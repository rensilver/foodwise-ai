"""Framework-independent catalog snapshots and fully prepared write bundles."""

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from food_recommender.domain.values import nonempty, unique


@dataclass(frozen=True, kw_only=True)
class Identity:
    id: str
    source_id: str
    source_record_id: str
    name: str

    def __post_init__(self) -> None:
        for value in (self.id, self.source_id, self.source_record_id, self.name):
            nonempty(value)


@dataclass(frozen=True, kw_only=True)
class RestaurantData(Identity):
    description: str | None = None
    cuisine: str | None = None
    normalized_cuisine: str | None = None
    location: str | None = None
    normalized_location: str | None = None
    restaurant_type: str | None = None
    rating: float | None = None
    price_band: int | None = None
    signatures: tuple[str, ...] | None = None
    vibe: str | None = None
    environment: str | None = None
    shortcomings: tuple[str, ...] | None = None
    availability: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    allergens: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for value, lower, upper in (
            (self.rating, 0, 5),
            (self.price_band, 1, 4),
            (self.latitude, -90, 90),
            (self.longitude, -180, 180),
        ):
            if value is not None and not lower <= value <= upper:
                raise ValueError("Catalog value outside supported range")
        if self.price_band is not None and type(self.price_band) is not int:
            raise ValueError("Price band must be an integer")


@dataclass(frozen=True, kw_only=True)
class RecipeData(Identity):
    cuisine: str | None = None
    normalized_cuisine: str | None = None
    servings: int | None = None
    prep_time: str | None = None
    cook_time: str | None = None
    total_time: str | None = None
    ingredients: tuple[str, ...] | None = None
    directions: tuple[str, ...] | None = None
    difficulty: str | None = None
    nutrition: dict[str, object] | None = None
    availability: str | None = None
    allergens: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.servings is not None and (
            type(self.servings) is not int or self.servings <= 0
        ):
            raise ValueError("Servings must be a positive integer")


type CatalogData = RestaurantData | RecipeData


@dataclass(frozen=True)
class CatalogSnapshot:
    data: CatalogData
    version: int


def sha256(value: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Expected SHA-256 digest")


@dataclass(frozen=True, kw_only=True)
class SourceData:
    id: str
    logical_source_id: str
    locator_kind: Literal["file", "url", "admin"]
    locator: str
    content_hash: str
    published_on: date | None = None
    retrieved_at: datetime | None = None

    def __post_init__(self) -> None:
        for value in (self.id, self.logical_source_id, self.locator):
            nonempty(value)
        sha256(self.content_hash)


@dataclass(frozen=True, kw_only=True)
class AttributedData:
    id: str
    content_hash: str
    ingestion_version: str
    attribution: Literal["source", "imported", "generated"]
    generator: str | None = None
    generator_revision: str | None = None
    input_hash: str | None = None

    def __post_init__(self) -> None:
        for value in (self.id, self.ingestion_version):
            nonempty(value)
        sha256(self.content_hash)
        if self.input_hash is not None:
            sha256(self.input_hash)
        for generator_value in (self.generator, self.generator_revision):
            if generator_value is not None:
                nonempty(generator_value)
        if self.attribution == "generated" and (
            self.generator is None or self.input_hash is None
        ):
            raise ValueError("Generated content requires generator and input hash")


@dataclass(frozen=True, kw_only=True)
class RecordData(AttributedData):
    source_id: str
    record_id: str
    record_type: Literal["restaurant", "recipe"]
    raw_payload: dict[str, object] | None = None
    raw_text: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        nonempty(self.source_id)
        nonempty(self.record_id)
        if self.raw_payload is None and self.raw_text is None:
            raise ValueError("Raw source content is required")


@dataclass(frozen=True, kw_only=True)
class DocumentData(AttributedData):
    source_record_id: str
    kind: str
    text: str
    media_id: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        for value in (self.source_record_id, self.kind, self.text):
            nonempty(value)
        if self.content_hash != hashlib.sha256(self.text.encode()).hexdigest():
            raise ValueError("Document hash must match prepared text")
        if (self.start_offset is None) != (self.end_offset is None):
            raise ValueError("Both chunk offsets are required")
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and not 0 <= self.start_offset < self.end_offset
        ):
            raise ValueError("Invalid chunk offsets")


@dataclass(frozen=True, kw_only=True)
class MediaData(AttributedData):
    source_record_id: str
    storage_key: str
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    byte_size: int
    width: int
    height: int
    original_locator: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        nonempty(self.source_record_id)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.storage_key) is None:
            raise ValueError("Media storage key must be a basename")
        if min(self.byte_size, self.width, self.height) <= 0:
            raise ValueError("Media size and dimensions must be positive")


@dataclass(frozen=True, kw_only=True)
class EmbeddingData:
    id: str
    parent_id: str
    model: str
    revision: str
    input_hash: str
    values: tuple[float, ...]

    def __post_init__(self) -> None:
        for value in (self.id, self.parent_id, self.revision):
            nonempty(value)
        sha256(self.input_hash)
        dimension = {
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "openai/clip-vit-base-patch32": 512,
        }.get(self.model)
        if dimension is None or len(self.values) != dimension:
            raise ValueError("Embedding model/dimension mismatch")
        if (
            not all(math.isfinite(value) for value in self.values)
            or not 0.999
            <= math.sqrt(sum(value * value for value in self.values))
            <= 1.001
        ):
            raise ValueError("Embeddings must be finite and normalized")


@dataclass(frozen=True)
class PreparedCatalog:
    data: CatalogData
    sources: tuple[SourceData, ...] = ()
    records: tuple[RecordData, ...] = ()
    documents: tuple[DocumentData, ...] = ()
    media: tuple[MediaData, ...] = ()
    text_embeddings: tuple[EmbeddingData, ...] = ()
    image_embeddings: tuple[EmbeddingData, ...] = ()

    def __post_init__(self) -> None:
        for values in (
            self.sources,
            self.records,
            self.documents,
            self.media,
            self.text_embeddings,
            self.image_embeddings,
        ):
            unique(tuple(value.id for value in values))
        sources = {item.id: item for item in self.sources}
        records = {item.id: item for item in self.records}
        documents = {item.id: item for item in self.documents}
        media = {item.id: item for item in self.media}
        category = "restaurant" if isinstance(self.data, RestaurantData) else "recipe"
        for record in self.records:
            if (
                record.source_id not in sources
                or record.record_type != category
                or sources[record.source_id].logical_source_id != self.data.source_id
            ):
                raise ValueError("Source records must belong to this catalog item")
        associated: tuple[DocumentData | MediaData, ...] = (
            *self.documents,
            *self.media,
        )
        for item in associated:
            if item.source_record_id not in records:
                raise ValueError("Prepared content requires its source record")
        for document in self.documents:
            if document.media_id is not None and (
                document.media_id not in media
                or media[document.media_id].source_record_id
                != document.source_record_id
            ):
                raise ValueError("Document/media source record mismatch")
        for vectors, parents, model in (
            (self.text_embeddings, documents, "sentence-transformers/all-MiniLM-L6-v2"),
            (self.image_embeddings, media, "openai/clip-vit-base-patch32"),
        ):
            unique(
                tuple(
                    (vector.parent_id, vector.model, vector.revision)
                    for vector in vectors
                )
            )
            for vector in vectors:
                if (
                    vector.model != model
                    or vector.parent_id not in parents
                    or vector.input_hash != parents[vector.parent_id].content_hash
                ):
                    raise ValueError("Embedding input/model must match prepared parent")
