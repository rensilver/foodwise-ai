"""Private file deletion by validated basename, without following symlinks."""

import asyncio
import os
import re
from pathlib import Path

from food_recommender.application.errors import ApplicationError, ErrorCode


class LocalMediaFiles:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute() or root == Path("/") or ".." in root.parts:
            raise ValueError("Media root must be an absolute non-root path")
        self.root = root

    async def delete(self, storage_key: str) -> None:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", storage_key) is None:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        try:
            await asyncio.to_thread(self._unlink, storage_key)
        except OSError as error:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from error

    def _unlink(self, storage_key: str) -> None:
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            # unlink removes the link itself, never its target. Missing files are
            # expected when retrying after a successful unlink/failed DB commit.
            try:
                os.unlink(storage_key, dir_fd=descriptor)
            except FileNotFoundError:
                pass
        finally:
            os.close(descriptor)

    async def read(self, storage_key: str) -> bytes:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", storage_key) is None:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        try:
            return await asyncio.to_thread(self._read, storage_key)
        except OSError as error:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from error

    def _read(self, storage_key: str) -> bytes:
        from food_recommender.infrastructure.media.images import MAX_BYTES

        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            descriptor = os.open(
                storage_key,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=directory,
            )
            with os.fdopen(descriptor, "rb") as file:
                import stat

                if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                    raise ValueError("Media must be a regular file")
                data = file.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("Media exceeds byte limit")
                return data
        finally:
            os.close(directory)

    async def write(self, storage_key: str, content: bytes) -> None:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", storage_key) is None:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        try:
            await asyncio.to_thread(self._write, storage_key, content)
        except OSError as error:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from error

    def _write(self, storage_key: str, content: bytes) -> None:
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            descriptor = os.open(
                storage_key,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(descriptor, "wb") as file:
                    file.write(content)
                    file.flush()
                    os.fsync(file.fileno())
            except BaseException:
                os.unlink(storage_key, dir_fd=directory)
                raise
        finally:
            os.close(directory)
