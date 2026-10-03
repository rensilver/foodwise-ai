"""Atomic PostgreSQL seed upserts and checkpoints without global index resets."""

from dataclasses import asdict
from datetime import datetime
from typing import Any, Literal, cast

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Text,
    delete,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.domain.catalog import RecipeData, RestaurantData
from food_recommender.infrastructure.catalog import Base, Recipe, Restaurant, Review
from food_recommender.infrastructure.cleanup import MediaCleanupJob
from food_recommender.infrastructure.context import DemoProfile
from food_recommender.infrastructure.provenance import (
    Document,
    Media,
    Source,
    SourceRecord,
)
from food_recommender.ingestion.adapters import INGESTION_VERSION, ReviewData
from food_recommender.ingestion.models import SeedItem


class IngestionCheckpoint(Base):
    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (
        CheckConstraint(
            "category IN ('restaurant', 'recipe', 'review')", name="category_values"
        ),
        CheckConstraint("entity_id ~ '[^[:space:]]'", name="entity_id_nonempty"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint_sha256"),
        CheckConstraint("catalog_version > 0", name="version_positive"),
    )
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_id: Mapped[str] = mapped_column(Text, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    ingestion_version: Mapped[str] = mapped_column(Text, nullable=False)
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class PostgresIngestionStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def upsert(self, item: SeedItem) -> Literal["imported", "unchanged"]:
        async with self.sessions() as session, session.begin():
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
                {"identity": f"foodwise-ingestion:{item.category}:{item.data.id}"},
            )
            model: type[Restaurant] | type[Recipe] | type[Review]
            model = (
                Restaurant
                if isinstance(item.data, RestaurantData)
                else Recipe
                if isinstance(item.data, RecipeData)
                else Review
            )
            current = cast(
                Restaurant | Recipe | Review | None,
                await session.get(model, item.data.id, with_for_update=True),
            )
            checkpoint = await session.get(
                IngestionCheckpoint, (item.category, item.data.id)
            )
            if current is not None and (
                checkpoint is None
                or current.version != checkpoint.catalog_version
                or (current.source_id, current.source_record_id)
                != (item.data.source_id, item.data.source_record_id)
            ):
                raise ApplicationError(ErrorCode.CONFLICT)
            if (
                current is not None
                and checkpoint is not None
                and checkpoint.fingerprint == item.fingerprint
            ):
                return "unchanged"
            if isinstance(item.data, ReviewData):
                await session.execute(
                    upsert(DemoProfile)
                    .values(id=item.data.demo_profile_id)
                    .on_conflict_do_nothing()
                )
            payload = asdict(item.data)
            version = 1 if current is None else current.version + 1
            if current is None:
                await session.execute(insert(model).values(**payload))
            else:
                for key in ("id", "source_id", "source_record_id"):
                    payload.pop(key)
                await session.execute(
                    update(model)
                    .where(model.id == item.data.id, model.version == current.version)
                    .values(**payload, version=version)
                )
            for source in item.sources:
                await self._immutable(session, Source, asdict(source))
            for record in item.records:
                await self._immutable(
                    session,
                    SourceRecord,
                    {**record, f"{item.category}_id": item.data.id},
                )
            record_ids = select(SourceRecord.id).where(
                getattr(SourceRecord, f"{item.category}_id") == item.data.id
            )
            # Only stale rows for this changed entity are invalidated. Unchanged
            # documents/media retain vectors; provenance revisions are retained.
            await session.execute(
                delete(Document).where(
                    Document.source_record_id.in_(record_ids),
                    Document.id.not_in([document.id for document in item.documents]),
                )
            )
            removed = (
                (
                    await session.execute(
                        delete(Media)
                        .where(
                            Media.source_record_id.in_(record_ids),
                            Media.id.not_in([media.id for media in item.media]),
                        )
                        .returning(Media.storage_key)
                    )
                )
                .scalars()
                .all()
            )
            for key in removed:
                await session.execute(
                    upsert(MediaCleanupJob)
                    .values(storage_key=key)
                    .on_conflict_do_nothing()
                )
            for media in item.media:
                await self._immutable(session, Media, asdict(media))
            for document in item.documents:
                await self._immutable(session, Document, asdict(document))
            statement = upsert(IngestionCheckpoint).values(
                category=item.category,
                entity_id=item.data.id,
                fingerprint=item.fingerprint,
                ingestion_version=INGESTION_VERSION,
                catalog_version=version,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[
                        IngestionCheckpoint.category,
                        IngestionCheckpoint.entity_id,
                    ],
                    set_={
                        "fingerprint": item.fingerprint,
                        "ingestion_version": INGESTION_VERSION,
                        "catalog_version": version,
                        "updated_at": text("now()"),
                    },
                )
            )
            return "imported"

    async def _immutable(
        self,
        session: AsyncSession,
        model: type[Source] | type[SourceRecord] | type[Media] | type[Document],
        values: dict[str, Any],
    ) -> None:
        # An ID denotes immutable content/provenance. Conflict is not a silent
        # overwrite, including collisions across concurrent imports.
        await session.execute(upsert(model).values(**values).on_conflict_do_nothing())
        existing = await session.get(model, values["id"])
        if existing is None or any(
            getattr(existing, key) != value for key, value in values.items()
        ):
            raise ApplicationError(ErrorCode.CONFLICT)
