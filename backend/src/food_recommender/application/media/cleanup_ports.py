"""File deletion and transactional cleanup queue contracts."""

from typing import Protocol


class MediaFiles(Protocol):
    async def delete(self, storage_key: str) -> None: ...


class MediaCleanupRepository(Protocol):
    async def has_pending(self, keys: tuple[str, ...]) -> bool: ...

    async def pending(
        self, *, limit: int, keys: tuple[str, ...] | None = None
    ) -> tuple[str, ...]: ...
    async def referenced(self, storage_key: str) -> bool: ...
    async def complete(self, storage_key: str) -> None: ...
