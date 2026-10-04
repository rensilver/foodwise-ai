"""PostgreSQL storage for bounded, dated trend evidence and cache entries."""

from datetime import datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.ports import CachedTrends, TrendItem
from food_recommender.infrastructure.persistence.models.trends import (
    TrendCache,
    TrendEvidence,
)


class PostgresTrendRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, query_hash: str, now: datetime) -> CachedTrends | None:
        if now.tzinfo is None:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        row = await self.session.scalar(
            select(TrendCache).where(
                TrendCache.query_hash == query_hash,
                TrendCache.retrieved_at <= now,
                TrendCache.expires_at > now,
            )
        )
        if row is None:
            return None
        evidence = (
            await self.session.scalars(
                select(TrendEvidence)
                .where(TrendEvidence.query_hash == query_hash)
                .order_by(TrendEvidence.position)
            )
        ).all()
        return CachedTrends(
            row.query_hash,
            row.query,
            row.retrieved_at,
            row.expires_at,
            tuple(
                TrendItem(
                    item.id,
                    item.url,
                    item.excerpt,
                    item.published_on,
                    item.retrieved_at,
                )
                for item in evidence
            ),
        )

    async def put(self, result: CachedTrends) -> None:
        if len(result.evidence) > 5:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        statement = upsert(TrendCache).values(
            query_hash=result.query_hash,
            query=result.query,
            retrieved_at=result.retrieved_at,
            expires_at=result.expires_at,
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[TrendCache.query_hash],
                set_={
                    "query": statement.excluded.query,
                    "retrieved_at": statement.excluded.retrieved_at,
                    "expires_at": statement.excluded.expires_at,
                },
            )
        )
        await self.session.execute(
            delete(TrendEvidence).where(TrendEvidence.query_hash == result.query_hash)
        )
        for position, item in enumerate(result.evidence):
            await self.session.execute(
                insert(TrendEvidence).values(
                    id=item.id,
                    query_hash=result.query_hash,
                    position=position,
                    url=item.url,
                    excerpt=item.excerpt,
                    published_on=item.published_on,
                    retrieved_at=item.retrieved_at,
                )
            )
