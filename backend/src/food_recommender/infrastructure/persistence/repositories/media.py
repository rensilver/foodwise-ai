"""Private session-owned upload metadata; paths never cross the HTTP boundary."""

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.media.ports import MediaReceipt, StoredMedia
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.persistence.models.provenance import (
    Media,
    SourceRecord,
)


class PostgresMediaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, owner: UUID, media: StoredMedia) -> None:
        item = media.receipt
        await self.session.execute(
            insert(Media).values(
                id=item.id,
                owner_session_id=owner,
                storage_key=media.storage_key,
                mime_type=item.mime_type,
                byte_size=item.byte_size,
                width=item.width,
                height=item.height,
                content_hash=media.content_hash,
                ingestion_version="upload-v1",
                attribution="source",
            )
        )

    async def get(self, owner: UUID, media_id: str) -> StoredMedia:
        row = await self.session.scalar(
            select(Media).where(Media.id == media_id, Media.owner_session_id == owner)
        )
        if row is None:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        return StoredMedia(
            MediaReceipt(row.id, row.mime_type, row.byte_size, row.width, row.height),
            row.storage_key,
            row.content_hash,
        )

    async def catalog_images(self, ref: EntityRef) -> tuple[MediaReceipt, ...]:
        link = (
            SourceRecord.restaurant_id
            if ref.category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        rows = (
            await self.session.scalars(
                select(Media)
                .join(SourceRecord, Media.source_record_id == SourceRecord.id)
                .where(link == ref.id, Media.owner_session_id.is_(None))
                .order_by(Media.id)
                .limit(20)
            )
        ).all()
        return tuple(
            MediaReceipt(row.id, row.mime_type, row.byte_size, row.width, row.height)
            for row in rows
        )

    async def catalog_image(self, ref: EntityRef, media_id: str) -> StoredMedia:
        link = (
            SourceRecord.restaurant_id
            if ref.category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        row = await self.session.scalar(
            select(Media)
            .join(SourceRecord, Media.source_record_id == SourceRecord.id)
            .where(
                link == ref.id, Media.id == media_id, Media.owner_session_id.is_(None)
            )
        )
        if row is None:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        return StoredMedia(
            MediaReceipt(row.id, row.mime_type, row.byte_size, row.width, row.height),
            row.storage_key,
            row.content_hash,
        )
