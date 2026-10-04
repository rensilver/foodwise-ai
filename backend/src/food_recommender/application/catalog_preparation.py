"""Immutable admin provenance and lossless culinary documents prepared before writes."""

import hashlib
import json
from dataclasses import asdict
from typing import Literal
from uuid import uuid4

from food_recommender.domain.catalog import (
    CatalogData,
    PreparedCatalog,
    RecordData,
    RestaurantData,
    SourceData,
)
from food_recommender.retrieval.documents import document, render


class CatalogPreparation:
    async def prepare(self, data: CatalogData) -> PreparedCatalog:
        category: Literal["restaurant", "recipe"] = (
            "restaurant" if isinstance(data, RestaurantData) else "recipe"
        )
        payload = json.loads(json.dumps(asdict(data)))
        serialized = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(serialized.encode()).hexdigest()
        revision = str(uuid4())
        source = SourceData(
            id="admin-source:" + revision,
            logical_source_id=data.source_id,
            locator_kind="admin",
            locator=f"admin/{category}/{data.id}",
            content_hash=digest,
        )
        record = RecordData(
            id="admin-record:" + revision,
            source_id=source.id,
            record_id=data.source_record_id,
            record_type=category,
            raw_payload=payload,
            content_hash=digest,
            ingestion_version="admin-v1",
            attribution="source",
        )
        text = render(category, payload)
        return PreparedCatalog(
            data,
            sources=(source,),
            records=(record,),
            documents=(document(record.id, category, text),),
        )
