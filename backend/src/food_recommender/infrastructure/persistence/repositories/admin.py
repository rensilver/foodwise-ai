"""Hash-only administrator session persistence."""

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from food_recommender.application.auth.ports import AdminRecord
from food_recommender.infrastructure.persistence.models.admin import AdminSession


class PostgresAdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: AdminRecord) -> None:
        await self.session.execute(
            insert(AdminSession).values(
                token_hash=record.token_hash,
                csrf_hash=record.csrf_hash,
                expires_at=record.expires_at,
            )
        )

    async def get(self, hashed_token: str) -> AdminRecord | None:
        row = await self.session.get(AdminSession, hashed_token)
        return (
            AdminRecord(row.token_hash, row.csrf_hash, row.expires_at) if row else None
        )

    async def delete(self, hashed_token: str) -> None:
        await self.session.execute(
            delete(AdminSession).where(AdminSession.token_hash == hashed_token)
        )
