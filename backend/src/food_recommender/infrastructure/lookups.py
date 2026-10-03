"""Parameterized exact names, lexical ambiance and explicitly scoped reviews."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.application.lookups import RestaurantMatch, ReviewMatch
from food_recommender.infrastructure.catalog import Restaurant, Review


class PostgresLookups:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    @staticmethod
    def _restaurant(row: Restaurant) -> RestaurantMatch:
        return RestaurantMatch(
            **{name: getattr(row, name) for name in RestaurantMatch.model_fields}
        )

    async def restaurants(self, name: str) -> tuple[RestaurantMatch, ...]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(Restaurant)
                .where(func.lower(Restaurant.name) == name.strip().lower())
                .order_by(Restaurant.id)
            )
            return tuple(self._restaurant(row) for row in rows)

    async def vibes(self, vibe: str, limit: int) -> tuple[RestaurantMatch, ...]:
        text = func.concat_ws(
            " ", Restaurant.vibe, Restaurant.environment, Restaurant.description
        )
        query = func.plainto_tsquery("english", vibe)
        vector = func.to_tsvector("english", text)
        async with self.sessions() as session:
            rows = await session.scalars(
                select(Restaurant)
                .where(vector.op("@@")(query))
                .order_by(func.ts_rank_cd(vector, query).desc(), Restaurant.id)
                .limit(limit)
            )
            return tuple(self._restaurant(row) for row in rows)

    async def reviews(
        self, restaurant_id: str, profile: str
    ) -> tuple[ReviewMatch, ...]:
        async with self.sessions() as session:
            rows = await session.scalars(
                select(Review)
                .where(
                    Review.restaurant_id == restaurant_id,
                    Review.demo_profile_id == profile,
                )
                .order_by(Review.id)
            )
            return tuple(
                ReviewMatch(
                    id=row.id,
                    restaurant_id=row.restaurant_id,
                    source_id=row.source_id,
                    source_record_id=row.source_record_id,
                    text=row.text,
                    published_on=row.published_on,
                )
                for row in rows
            )
