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
