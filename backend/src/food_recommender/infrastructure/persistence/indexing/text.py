"""Hash-idempotent document/vector batches, prepared before atomic persistence."""

import asyncio
import hashlib
from dataclasses import asdict, replace
from typing import Literal, cast

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.domain.catalog import DocumentData, EmbeddingData
from food_recommender.infrastructure.persistence.models.embeddings import TextEmbedding
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    SourceRecord,
)
from food_recommender.retrieval.chunking import chunks
from food_recommender.retrieval.documents import VERSION, document, render
from food_recommender.retrieval.ports import TextEncoder


class TextIndexer:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], encoder: TextEncoder
    ) -> None:
        self.sessions = sessions
        self.encoder = encoder

    def prepare(
        self, record: SourceRecord, captions: tuple[Document, ...]
    ) -> tuple[DocumentData, ...]:
        text = render(
            record.record_type,
            record.raw_payload if isinstance(record.raw_payload, dict) else None,
            record.raw_text,
        )
        prepared = (
            [
                document(record.id, record.record_type, text, start=a, end=b)
                for a, b in chunks(
                    text, self.encoder.offsets, max_tokens=self.encoder.max_tokens
                )
            ]
            if text.strip()
            else []
        )
        for caption in captions:
            for a, b in chunks(
                caption.text, self.encoder.offsets, max_tokens=self.encoder.max_tokens
            ):
                chunk = document(
                    record.id, f"caption:{caption.id}", caption.text, start=a, end=b
                )
                prepared.append(
                    replace(
                        chunk,
                        id=hashlib.sha256(
                            f"{chunk.id}:{caption.attribution}:{caption.generator}:{caption.generator_revision}:{caption.media_id}".encode()
                        ).hexdigest(),
                        attribution=cast(
                            Literal["source", "imported", "generated"],
                            caption.attribution,
                        ),
                        generator=caption.generator,
                        generator_revision=caption.generator_revision,
                        input_hash=caption.input_hash,
                        media_id=caption.media_id,
                    )
                )
        return tuple(prepared)

    async def build(self, *, batch_size: int = 32) -> dict[str, int]:
        if not 1 <= batch_size <= 128:
            raise ValueError("Index batch size must be 1..128")
        counts = {"documents": 0, "embedded": 0, "unchanged": 0}
        async with self.sessions() as session:
            record_ids = (
                await session.scalars(
                    select(SourceRecord.id)
                    .where(
                        (SourceRecord.restaurant_id.is_not(None))
                        | (SourceRecord.recipe_id.is_not(None))
                        | (SourceRecord.review_id.is_not(None))
                    )
                    .order_by(SourceRecord.id)
                )
            ).all()
        for record_id in record_ids:
            async with self.sessions() as session:
                record = await session.get(SourceRecord, record_id)
                if record is None:
                    raise ValueError("Source changed during indexing")
                captions = tuple(
                    (
                        await session.scalars(
                            select(Document).where(
                                Document.source_record_id == record_id,
                                Document.kind == "image_caption",
                            )
                        )
                    ).all()
                )
                prepared = await asyncio.to_thread(self.prepare, record, captions)
                existing = dict(
                    (
                        await session.execute(
                            select(
                                TextEmbedding.document_id, TextEmbedding.input_hash
                            ).where(
                                TextEmbedding.document_id.in_([d.id for d in prepared]),
                                TextEmbedding.model == self.encoder.model_id,
                                TextEmbedding.revision == self.encoder.revision,
                            )
                        )
                    ).all()
                )
            counts["documents"] += len(prepared)
            counts["unchanged"] += sum(
                existing.get(d.id) == d.content_hash for d in prepared
            )
            pending = [d for d in prepared if existing.get(d.id) != d.content_hash]
            for offset in range(0, len(pending), batch_size):
                batch = pending[offset : offset + batch_size]
                vectors = await asyncio.to_thread(
                    self.encoder.encode, tuple(d.text for d in batch)
                )
                if len(vectors) != len(batch):
                    raise ValueError("Encoder output count mismatch")
                embeddings = tuple(
                    EmbeddingData(
                        id=f"{d.id}:{self.encoder.revision}",
                        parent_id=d.id,
                        model=self.encoder.model_id,
                        revision=self.encoder.revision,
                        input_hash=d.content_hash,
                        values=v,
                    )
                    for d, v in zip(batch, vectors, strict=True)
                )
                async with self.sessions() as session, session.begin():
                    current = await session.get(
                        SourceRecord, record_id, with_for_update=True
                    )
                    if current is None or current.content_hash != record.content_hash:
                        raise ValueError("Source changed during indexing")
                    for d, vector in zip(batch, embeddings, strict=True):
                        await session.execute(
                            insert(Document)
                            .values(**asdict(d))
                            .on_conflict_do_nothing()
                        )
                        statement = insert(TextEmbedding).values(
                            id=vector.id,
                            document_id=d.id,
                            model=vector.model,
                            revision=vector.revision,
                            input_hash=vector.input_hash,
                            dimension=384,
                            embedding=list(vector.values),
                        )
                        await session.execute(
                            statement.on_conflict_do_update(
                                index_elements=[
                                    TextEmbedding.document_id,
                                    TextEmbedding.model,
                                    TextEmbedding.revision,
                                ],
                                set_={
                                    "embedding": list(vector.values),
                                    "input_hash": vector.input_hash,
                                },
                            )
                        )
                counts["embedded"] += len(batch)
            # Remove only obsolete projections after replacements succeed. Original
            # records/captions/media and their source history remain untouched.
            async with self.sessions() as session, session.begin():
                await session.execute(
                    delete(Document).where(
                        Document.source_record_id == record_id,
                        Document.ingestion_version == VERSION,
                        Document.id.not_in([d.id for d in prepared]),
                    )
                )
        return counts
