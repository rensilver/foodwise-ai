"""Lossless documents and compatible embeddings prepared before final writes."""

import asyncio
import hashlib
import json
from dataclasses import asdict
from typing import Literal

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.domain.catalog import (
    CatalogData,
    EmbeddingData,
    PreparedCatalog,
    RecordData,
    RestaurantData,
    SourceData,
)
from food_recommender.retrieval.chunking import chunks
from food_recommender.retrieval.documents import document, render
from food_recommender.retrieval.embedding_contracts import validate_query
from food_recommender.retrieval.ports import TextEncoder


class CatalogPreparation:
    def __init__(self, encoder: TextEncoder | None = None) -> None:
        self.encoder = encoder
        self.slots = asyncio.Semaphore(1)

    async def prepare(self, data: CatalogData) -> PreparedCatalog:
        if self.encoder is None:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        async with self.slots:
            try:
                return await asyncio.to_thread(self._prepare, data, self.encoder)
            except (ValueError, OSError, RuntimeError):
                raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None

    def _prepare(self, data: CatalogData, encoder: TextEncoder) -> PreparedCatalog:
        category: Literal["restaurant", "recipe"] = (
            "restaurant" if isinstance(data, RestaurantData) else "recipe"
        )
        payload = json.loads(json.dumps(asdict(data)))
        serialized = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        # Deterministic immutable revisions allow no-op content updates to reuse
        # the same provenance without conflicting on the source uniqueness key.
        source = SourceData(
            id="admin-source:" + digest,
            logical_source_id=data.source_id,
            locator_kind="admin",
            locator=f"admin/{category}/{data.id}",
            content_hash=digest,
        )
        record = RecordData(
            id="admin-record:" + digest,
            source_id=source.id,
            record_id=data.source_record_id,
            record_type=category,
            raw_payload=payload,
            content_hash=digest,
            ingestion_version="admin-v1",
            attribution="source",
        )
        text = render(category, payload)
        documents = tuple(
            document(record.id, category, text, start=start, end=end)
            for start, end in chunks(
                text, encoder.offsets, max_tokens=encoder.max_tokens
            )
        )
        embeddings = []
        for position in range(0, len(documents), 32):
            batch = documents[position : position + 32]
            vectors = encoder.encode(tuple(item.text for item in batch))
            if len(vectors) != len(batch):
                raise ValueError("Embedding count mismatch")
            for item, vector in zip(batch, vectors, strict=True):
                validate_query(vector, encoder.model_id, encoder.revision)
                embeddings.append(
                    EmbeddingData(
                        id="admin-vector:" + item.id,
                        parent_id=item.id,
                        model=encoder.model_id,
                        revision=encoder.revision,
                        input_hash=item.content_hash,
                        values=vector,
                    )
                )
        return PreparedCatalog(
            data,
            sources=(source,),
            records=(record,),
            documents=documents,
            text_embeddings=tuple(embeddings),
            preserve_media=True,
        )
