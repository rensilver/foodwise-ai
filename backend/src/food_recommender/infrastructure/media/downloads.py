"""Bounded course-host HTTP downloads with DNS pinning and redirect validation."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable

import httpx

from food_recommender.ingestion.adapters import SourceError, digest
from food_recommender.ingestion.images import MAX_BYTES

APPROVED_HOSTS = frozenset(
    {"cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud"}
)


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
