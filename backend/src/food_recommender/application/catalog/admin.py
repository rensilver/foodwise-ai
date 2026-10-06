"""Explicit catalog mutations and non-persisting structured extraction previews."""

from dataclasses import asdict
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from food_recommender.application.catalog.browse import BrowseService
from food_recommender.application.catalog.service import CatalogService
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.domain.catalog import (
    CatalogData,
    CatalogSnapshot,
    PreparedCatalog,
    RecipeData,
    RestaurantData,
)
from food_recommender.domain.values import Category, EntityRef
from food_recommender.ingestion.adapters import duration, normalize
from food_recommender.ingestion.extraction import (
    ExtractionResult,
    RecipeFields,
    RestaurantFields,
)


class CatalogPreparer(Protocol):
    async def prepare(self, data: CatalogData) -> PreparedCatalog: ...


class ExtractionPreview(Protocol):
    async def preview(self, text: str, category: Category) -> ExtractionResult: ...


class RestaurantPatch(RestaurantFields):
    name: str = Field(default="", min_length=1, max_length=500, pattern=r"\S")


class RecipePatch(RecipeFields):
    name: str = Field(default="", min_length=1, max_length=500, pattern=r"\S")


class AdminCatalogService:
    def __init__(
        self,
        catalog: CatalogService,
        browse: BrowseService,
        preparer: CatalogPreparer,
        extraction: ExtractionPreview,
    ) -> None:
        self.catalog, self.browse, self.preparer, self.extraction = (
            catalog,
            browse,
            preparer,
            extraction,
        )

    async def preview(self, text: str, category: Category) -> ExtractionResult:
        return await self.extraction.preview(text, category)

    def _data(
        self,
        category: Category,
        fields: dict[str, Any],
        *,
        original: CatalogData | None = None,
    ) -> CatalogData:
        schema: type[BaseModel] = (
            RestaurantFields if category == Category.RESTAURANT else RecipeFields
        )
        validated = schema.model_validate(fields).model_dump()
        if category == Category.RECIPE:
            try:
                for key in ("prep_time", "cook_time", "total_time"):
                    duration(validated.get(key))
            except ValueError:
                raise ApplicationError(ErrorCode.INVALID_REQUEST) from None
        for key in ("signatures", "shortcomings", "ingredients", "directions"):
            if validated.get(key) is not None:
                values = validated[key]
                if len(values) > 1000 or any(
                    not item.strip() or len(item) > 4000 for item in values
                ):
                    raise ApplicationError(ErrorCode.INVALID_REQUEST)
                validated[key] = tuple(values)
        identity = str(uuid4()) if original is None else original.id
        source_id = "local-admin" if original is None else original.source_id
        record_id = identity if original is None else original.source_record_id
        common = dict(
            id=identity,
            source_id=source_id,
            source_record_id=record_id,
            normalized_cuisine=normalize(validated.get("cuisine")),
            **validated,
        )
        merged = {**asdict(original), **common} if original else common
        if category == Category.RESTAURANT:
            return (
                RestaurantData(
                    **merged, normalized_location=normalize(validated.get("location"))
                )
                if not original
                else RestaurantData(
                    **{
                        **merged,
                        "normalized_location": normalize(validated.get("location")),
                    }
                )
            )
        return RecipeData(**merged)

    async def create(
        self, category: Category, fields: dict[str, Any]
    ) -> CatalogSnapshot:
        data = self._data(category, fields)
        prepared = await self.preparer.prepare(data)
        return await self.catalog.create(prepared)

    async def update(
        self, ref: EntityRef, fields: dict[str, Any], expected_version: int
    ) -> CatalogSnapshot:
        if not fields:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        current = await self.browse.detail(ref)
        if current.version != expected_version:
            raise ApplicationError(ErrorCode.CONFLICT)
        original = asdict(current.data)
        schema = (
            RestaurantFields if ref.category == Category.RESTAURANT else RecipeFields
        )
        merged = {key: original[key] for key in schema.model_fields}
        # Convert domain tuples to the strict extraction schema's list fields.
        merged = {
            key: list(value) if isinstance(value, tuple) else value
            for key, value in merged.items()
        }
        merged.update(fields)
        data = self._data(ref.category, merged, original=current.data)
        prepared = await self.preparer.prepare(data)
        return await self.catalog.replace(
            ref, prepared, expected_version=expected_version
        )

    async def delete(
        self, ref: EntityRef, expected_version: int, confirm_id: str
    ) -> None:
        if confirm_id != ref.id:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        await self.catalog.delete(
            ref, expected_version=expected_version, include_reviews=True
        )
