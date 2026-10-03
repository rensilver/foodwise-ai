"""Bounded course-media fetching, decoding and identity-based ZIP ingestion."""

import asyncio
import hashlib
import io
import ipaddress
import os
import re
import socket
import stat
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import httpx
from PIL import Image

from food_recommender.ingestion.adapters import SourceError, digest

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
APPROVED_HOSTS = frozenset(
    {"cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud"}
)


@dataclass(frozen=True)
class PreparedImage:
    storage_key: str
    content_hash: str
    input_hash: str
    mime_type: str
    byte_size: int
    width: int
    height: int


def prepare_image(
    content: bytes, root: Path | None, *, namespace: str = "image"
) -> PreparedImage:
    if not 0 < len(content) <= MAX_BYTES:
        raise SourceError("image", namespace, "Image exceeds byte limit or is empty")
    try:
        with Image.open(io.BytesIO(content)) as image:
            if (
                image.format not in {"JPEG", "PNG", "WEBP"}
                or image.width * image.height > MAX_PIXELS
                or getattr(image, "n_frames", 1) != 1
            ):
                raise ValueError("Unsupported format, dimensions or animation")
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image.load()
            mode = (
                "RGBA"
                if "A" in image.getbands() or "transparency" in image.info
                else "RGB"
            )
            clean = Image.new(mode, image.size)
            clean.paste(image.convert(mode))
            output = io.BytesIO()
            clean.save(output, format="PNG")
            encoded = output.getvalue()
            width, height = clean.size
        if len(encoded) > MAX_BYTES:
            raise ValueError("Decoded image exceeds stored byte limit")
    except (OSError, ValueError, Image.DecompressionBombError):
        raise SourceError(
            "image", namespace, "Image cannot be decoded within limits"
        ) from None
    content_hash = hashlib.sha256(encoded).hexdigest()
    key = digest([namespace, content_hash]) + ".png"
    result = PreparedImage(
        key,
        content_hash,
        hashlib.sha256(content).hexdigest(),
        "image/png",
        len(encoded),
        width,
        height,
    )
    if root is None:
        return result
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    from uuid import uuid4

    temporary = f".pending-{uuid4().hex}"
    try:
        target = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=descriptor,
        )
        with os.fdopen(target, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(
                temporary,
                key,
                src_dir_fd=descriptor,
                dst_dir_fd=descriptor,
                follow_symlinks=False,
            )
        except FileExistsError:
            target = os.open(key, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
            with os.fdopen(target, "rb") as handle:
                if handle.read(MAX_BYTES + 1) != encoded:
                    raise SourceError(
                        "media storage", namespace, "Existing file content mismatch"
                    )
        os.fsync(descriptor)
    finally:
        try:
            os.unlink(temporary, dir_fd=descriptor)
        except FileNotFoundError:
            pass
        os.close(descriptor)
    return result


@dataclass(frozen=True)
class ArchiveReport:
    images: dict[str, PreparedImage]
    missing: tuple[str, ...]
    extra: tuple[str, ...]


def recipe_archive(path: Path, recipe_ids: set[str], root: Path) -> ArchiveReport:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if (
                not infos
                or len(infos) > 1000
                or sum(info.file_size for info in infos) > 512 * 1024 * 1024
            ):
                raise ValueError("Empty or oversized archive")
            members = {}
            names = set()
            for info in infos:
                name = info.filename
                parts = PurePosixPath(name).parts
                mode = info.external_attr >> 16
                if (
                    name in names
                    or "\\" in name
                    or name.startswith("/")
                    or ".." in parts
                    or stat.S_ISLNK(mode)
                    or info.flag_bits & 1
                ):
                    raise ValueError("Unsafe or duplicate archive member")
                names.add(name)
                if info.is_dir():
                    if name != "synthetic_recipe_images/":
                        raise ValueError("Unexpected archive directory")
                    continue
                match = re.fullmatch(
                    r"(?:synthetic_recipe_images/)?recipe([1-9][0-9]*)\.png", name
                )
                if (
                    match is None
                    or not 0 < info.file_size <= MAX_BYTES
                    or info.file_size / max(info.compress_size, 1) > 200
                ):
                    raise ValueError("Invalid filename or expansion bounds")
                recipe_id = match[1]
                if recipe_id in members:
                    raise ValueError("Duplicate recipe image identity")
                members[recipe_id] = info
            if not members or archive.testzip() is not None:
                raise ValueError("Empty archive or CRC failure")
            images = {}
            for recipe_id, info in members.items():
                # Decode even extra images so the complete archive is validated.
                image = prepare_image(
                    archive.read(info),
                    root if recipe_id in recipe_ids else None,
                    namespace=f"course-recipe:{recipe_id}",
                )
                if recipe_id in recipe_ids:
                    images[recipe_id] = image
            return ArchiveReport(
                images,
                tuple(sorted(recipe_ids - members.keys())),
                tuple(sorted(members.keys() - recipe_ids)),
            )
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as error:
        if isinstance(error, SourceError):
            raise
        raise SourceError(
            path.name, "?", "Archive failed integrity, path or size validation"
        ) from None


async def public_addresses(host: str) -> list[str]:
    records = await asyncio.get_running_loop().getaddrinfo(
        host, 443, type=socket.SOCK_STREAM
    )
    return sorted({str(record[4][0]) for record in records})


class CourseDownloader:
    """Production callers supply a TLS-verifying client with trust_env=False.

    Resolve once per hop, reject every non-public answer and pin the connection
    to an approved IP while retaining the original TLS hostname and Host header.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        resolve: Callable[[str], Awaitable[list[str]]] = public_addresses,
    ) -> None:
        self.client = client
        self.resolve = resolve

    async def download(self, locator: str) -> bytes:
        try:
            async with asyncio.timeout(60):
                return await self._download(locator)
        except (httpx.HTTPError, TimeoutError, OSError, ValueError):
            raise SourceError(
                "course image download",
                digest(locator),
                "Download failed host, address, redirect, timeout or size validation",
            ) from None

    async def _download(self, locator: str) -> bytes:
        url = httpx.URL(locator)
        for hop in range(4):
            if (
                url.scheme != "https"
                or url.host not in APPROVED_HOSTS
                or url.userinfo
                or url.fragment
                or url.port not in {None, 443}
            ):
                raise ValueError("Unapproved image URL")
            addresses = await self.resolve(url.host)
            if not addresses or any(
                not ipaddress.ip_address(address).is_global
                or ipaddress.ip_address(address).is_multicast
                for address in addresses
            ):
                raise ValueError("Nonpublic DNS answer")
            pinned = url.copy_with(host=addresses[0])
            async with self.client.stream(
                "GET",
                pinned,
                headers={"Host": url.host},
                extensions={"sni_hostname": url.host},
                follow_redirects=False,
                timeout=30,
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if hop == 3 or "location" not in response.headers:
                        raise ValueError("Redirect limit or missing target")
                    url = url.join(response.headers["location"])
                    continue
                response.raise_for_status()
                if int(response.headers.get("content-length", "0")) > MAX_BYTES:
                    raise ValueError("Oversized response")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_BYTES:
                        raise ValueError("Oversized response")
                if not content:
                    raise ValueError("Empty response")
                return bytes(content)
        raise ValueError("Redirect limit")
