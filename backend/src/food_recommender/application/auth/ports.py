"""Administrator session values, password verification and persistence ports."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AdminGrant:
    token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True)
class AdminRecord:
    token_hash: str
    csrf_hash: str
    expires_at: datetime


class PasswordVerification(Protocol):
    async def verify(self, password: str) -> bool: ...


class AdminRepository(Protocol):
    async def create(self, record: AdminRecord) -> None: ...
    async def get(self, hashed_token: str) -> AdminRecord | None: ...
    async def delete(self, hashed_token: str) -> None: ...
