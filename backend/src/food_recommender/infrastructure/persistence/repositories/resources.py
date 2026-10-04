"""Database projections exclude reviews, uploaded media and private histories."""

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.infrastructure.persistence.models.provenance import (
    Source,
    SourceRecord,
)


class PostgresCatalogResources:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read(self, name: str) -> str:
        public = SourceRecord.record_type.in_(("restaurant", "recipe"))
        async with self.sessions() as session:
            if name == "culinary-map":
                paragraphs = await session.scalars(
                    select(SourceRecord.raw_text)
                    .join(Source)
                    .where(public, Source.locator == "data/California-Culinary-Map.txt")
                    .order_by(SourceRecord.record_id)
                )
                return "\n\n".join(text for text in paragraphs if text is not None)
            if name == "dataset-manifest":
                rows = (
                    (
                        await session.execute(
                            select(
                                Source.logical_source_id,
                                Source.content_hash,
                                func.count(SourceRecord.id).label("records"),
                            )
                            .join(SourceRecord)
                            .where(public)
                            .group_by(Source.logical_source_id, Source.content_hash)
                            .order_by(Source.logical_source_id, Source.content_hash)
                        )
                    )
                    .mappings()
                    .all()
                )
            elif name == "source-provenance":
                rows = (
                    (
                        await session.execute(
                            select(
                                Source.id.label("source_id"),
                                Source.logical_source_id,
                                Source.content_hash.label("source_hash"),
                                SourceRecord.record_id,
                                SourceRecord.record_type,
                                SourceRecord.content_hash,
                                SourceRecord.ingestion_version,
                                SourceRecord.attribution,
                            )
                            .join(SourceRecord)
                            .where(public)
                            .order_by(Source.id, SourceRecord.record_id)
                        )
                    )
                    .mappings()
                    .all()
                )
            else:
                raise ValueError("Unknown fixed catalog resource")
            return json.dumps(
                {
                    "catalog": "Synthetic course catalog",
                    "records": [dict(row) for row in rows],
                }
            )
