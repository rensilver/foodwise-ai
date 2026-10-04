"""Durable media cleanup queue with locking and reference checks."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.infrastructure.persistence.models.cleanup import MediaCleanupJob
from food_recommender.infrastructure.persistence.models.provenance import Media


class PostgresMediaCleanupRepository:
    async def has_pending(self, keys: tuple[str, ...]) -> bool:
        return (
            await self.session.scalar(
                select(MediaCleanupJob.storage_key)
                .where(MediaCleanupJob.storage_key.in_(keys))
                .limit(1)
            )
            is not None
        )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def pending(
        self, *, limit: int, keys: tuple[str, ...] | None = None
    ) -> tuple[str, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        statement = (
            select(MediaCleanupJob.storage_key)
            .order_by(MediaCleanupJob.created_at, MediaCleanupJob.storage_key)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if keys is not None:
            statement = statement.where(MediaCleanupJob.storage_key.in_(keys))
        return tuple((await self.session.scalars(statement)).all())

    async def referenced(self, storage_key: str) -> bool:
        return (
            await self.session.scalar(
                select(Media.id).where(Media.storage_key == storage_key).limit(1)
            )
            is not None
        )

    async def complete(self, storage_key: str) -> None:
        await self.session.execute(
            delete(MediaCleanupJob).where(MediaCleanupJob.storage_key == storage_key)
        )
