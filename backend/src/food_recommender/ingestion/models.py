"""Prepared seed bundles and a narrow transactional ingestion boundary."""

from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol

from food_recommender.domain.catalog import (
    DocumentData,
    MediaData,
    RecipeData,
    RestaurantData,
    SourceData,
)
from food_recommender.ingestion.adapters import INGESTION_VERSION, SeedData, digest


@dataclass(frozen=True)
class SeedItem:
    data: SeedData
    sources: tuple[SourceData, ...] = ()
    records: tuple[dict[str, Any], ...] = ()
    documents: tuple[DocumentData, ...] = ()
    media: tuple[MediaData, ...] = ()
    # Fingerprint inputs exclude whole-file revisions, so unrelated source edits
    # do not reimport unchanged records or repeat their inference.
    inputs: tuple[Any, ...] = ()

    @property
    def category(self) -> Literal["restaurant", "recipe", "review"]:
        return (
            "restaurant"
            if isinstance(self.data, RestaurantData)
            else "recipe"
            if isinstance(self.data, RecipeData)
            else "review"
        )

    @property
    def fingerprint(self) -> str:
        data = asdict(self.data)
        if data.get("published_on") is not None:
            data["published_on"] = data["published_on"].isoformat()
        return digest(
            [
                INGESTION_VERSION,
                self.category,
                data,
                self.inputs,
                [
                    (
                        document.content_hash,
                        document.attribution,
                        document.generator,
                        document.generator_revision,
                        document.input_hash,
                    )
                    for document in self.documents
                ],
                [(item.content_hash, item.original_locator) for item in self.media],
            ]
        )


class IngestionStore(Protocol):
    async def upsert(self, item: SeedItem) -> Literal["imported", "unchanged"]: ...
