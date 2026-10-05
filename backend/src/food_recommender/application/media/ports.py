"""Owned media values and storage, decoding and persistence contracts."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class MediaReceipt:
    id: str
    mime_type: str
    byte_size: int
    width: int
    height: int


@dataclass(frozen=True)
class StoredMedia:
    receipt: MediaReceipt
    storage_key: str
    content_hash: str


@dataclass(frozen=True)
class SanitizedImage:
    content: bytes
    mime_type: str
    width: int
    height: int


class ImageSanitization(Protocol):
    async def prepare(self, content: bytes, mime_type: str) -> SanitizedImage: ...


class UploadFiles(Protocol):
    async def write(self, storage_key: str, content: bytes) -> None: ...
    async def read(self, storage_key: str) -> bytes: ...
    async def delete(self, storage_key: str) -> None: ...


class MediaRepository(Protocol):
    async def create(self, owner: UUID, media: StoredMedia) -> None: ...
    async def get(self, owner: UUID, media_id: str) -> StoredMedia: ...
