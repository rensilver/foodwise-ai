"""Idempotent CLIP batches; validate media bytes and links before committing."""

import asyncio
import hashlib
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.domain.catalog import DocumentData
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.persistence.models.embeddings import ImageEmbedding
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    Media,
    SourceRecord,
)
from food_recommender.retrieval.embedding_contracts import validate_clip
from food_recommender.retrieval.ports import ImageEncoder


class ImageIndexer:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        encoder: ImageEncoder,
        files: LocalMediaFiles,
    ) -> None:
        self.sessions, self.encoder, self.files = sessions, encoder, files

    async def build(self, *, batch_size: int = 16) -> dict[str, int]:
        if type(batch_size) is not int or not 1 <= batch_size <= 32:
            raise ValueError("Image batch size must be 1..32")
        async with self.sessions() as session:
            media = tuple(
                (
                    await session.scalars(
                        select(Media)
                        .join(SourceRecord, SourceRecord.id == Media.source_record_id)
                        .where(
                            (SourceRecord.recipe_id.is_not(None))
                            | (SourceRecord.review_id.is_not(None))
                            | (SourceRecord.restaurant_id.is_not(None))
                        )
                        .order_by(Media.id)
                    )
                ).all()
            )
            existing = dict(
                (
                    await session.execute(
                        select(
                            ImageEmbedding.media_id, ImageEmbedding.input_hash
                        ).where(
                            ImageEmbedding.model == self.encoder.model_id,
                            ImageEmbedding.revision == self.encoder.revision,
                        )
                    )
                ).all()
            )
        counts = {"media": len(media), "embedded": 0, "unchanged": 0}
        for offset in range(0, len(media), batch_size):
            batch = media[offset : offset + batch_size]
            pending, images = [], []
            for item in batch:
                data = await self.files.read(item.storage_key)
                if hashlib.sha256(data).hexdigest() != item.content_hash:
                    raise ValueError("Media hash mismatch")
                if existing.get(item.id) == item.content_hash:
                    counts["unchanged"] += 1
                else:
                    pending.append(item)
                    images.append(data)
            vectors = await asyncio.to_thread(self.encoder.encode_images, tuple(images))
            if len(vectors) != len(pending):
                raise ValueError("Image encoder count mismatch")
            for vector in vectors:
                validate_clip(vector, self.encoder.model_id, self.encoder.revision)
            async with self.sessions() as session, session.begin():
                for item, vector in zip(pending, vectors, strict=True):
                    current = await session.get(Media, item.id, with_for_update=True)
                    if current is None or (
                        current.content_hash,
                        current.source_record_id,
                        current.storage_key,
                    ) != (item.content_hash, item.source_record_id, item.storage_key):
                        raise ValueError("Media changed during indexing")
                    record = await session.get(SourceRecord, item.source_record_id)
                    if record is None:
                        raise ValueError("Media source disappeared")
                    text = f"Catalog image associated with {record.record_type} source record {record.record_id}. Visual similarity does not establish ingredients."
                    doc = DocumentData(
                        id=f"image:{item.id}",
                        source_record_id=record.id,
                        media_id=item.id,
                        kind="image_association",
                        text=text,
                        content_hash=hashlib.sha256(text.encode()).hexdigest(),
                        ingestion_version="clip-index-v1",
                        attribution="imported",
                    )
                    await session.execute(
                        insert(Document).values(**asdict(doc)).on_conflict_do_nothing()
                    )
                    statement = insert(ImageEmbedding).values(
                        id=f"{item.id}:{self.encoder.revision}",
                        media_id=item.id,
                        model=self.encoder.model_id,
                        revision=self.encoder.revision,
                        input_hash=item.content_hash,
                        dimension=512,
                        embedding=list(vector),
                    )
                    await session.execute(
                        statement.on_conflict_do_update(
                            index_elements=[
                                ImageEmbedding.media_id,
                                ImageEmbedding.model,
                                ImageEmbedding.revision,
                            ],
                            set_={
                                "input_hash": item.content_hash,
                                "embedding": list(vector),
                            },
                        )
                    )
            counts["embedded"] += len(pending)
        return counts
