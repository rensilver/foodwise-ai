"""Separate local administration authority with expiring, revocable sessions."""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.ports import UnitOfWork


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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


class AdminService:
    def __init__(
        self,
        transactions: Callable[[], UnitOfWork],
        passwords: PasswordVerification,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.transactions, self.passwords, self.clock = transactions, passwords, clock

    async def login(self, password: str, previous: str | None = None) -> AdminGrant:
        if not await self.passwords.verify(password):
            raise ApplicationError(ErrorCode.UNAUTHORIZED)
        grant = AdminGrant(
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(32),
            self.clock() + timedelta(hours=8),
        )
        async with self.transactions() as transaction:
            if previous:
                await transaction.admin.delete(token_hash(previous))
            await transaction.admin.create(
                AdminRecord(
                    token_hash(grant.token),
                    token_hash(grant.csrf_token),
                    grant.expires_at,
                )
            )
            await transaction.commit()
        return grant

    async def authorize(self, token: str | None, csrf_token: str | None) -> None:
        if not token or len(token) != 43:
            raise ApplicationError(ErrorCode.UNAUTHORIZED)
        async with self.transactions() as transaction:
            record = await transaction.admin.get(token_hash(token))
        if record is None or record.expires_at <= self.clock():
            raise ApplicationError(ErrorCode.UNAUTHORIZED)
        if not csrf_token or not secrets.compare_digest(
            record.csrf_hash, token_hash(csrf_token)
        ):
            raise ApplicationError(ErrorCode.FORBIDDEN)

    async def logout(self, token: str) -> None:
        async with self.transactions() as transaction:
            await transaction.admin.delete(token_hash(token))
            await transaction.commit()
