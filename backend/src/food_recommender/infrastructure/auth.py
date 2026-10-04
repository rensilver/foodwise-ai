"""Bounded Argon2id verification off the application event loop."""

import asyncio

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2Verification:
    def __init__(self, configured_hash: str) -> None:
        self.hash = configured_hash
        self.slots = asyncio.Semaphore(1)
        self.hasher = PasswordHasher()

    async def verify(self, password: str) -> bool:
        if not 1 <= len(password) <= 1024:
            return False
        async with self.slots:
            return await asyncio.to_thread(self._verify, password)

    def _verify(self, password: str) -> bool:
        try:
            return self.hasher.verify(self.hash, password)
        except (VerificationError, InvalidHashError):
            return False
