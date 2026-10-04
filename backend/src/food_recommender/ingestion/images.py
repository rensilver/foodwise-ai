"""Bounded course-media fetching, decoding and identity-based ZIP ingestion."""

import hashlib
import io
import os
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from PIL import Image

from food_recommender.ingestion.adapters import SourceError, digest

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000


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
