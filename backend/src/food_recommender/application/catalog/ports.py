"""Persistence contract for atomic catalog operations and source-backed reads."""

from typing import Protocol

from food_recommender.domain.catalog import CatalogSnapshot, PreparedCatalog
from food_recommender.domain.evidence import Citation
from food_recommender.domain.values import Category, EntityRef


class CatalogRepository(Protocol):
    async def browse(
        self, category: Category, filters: dict[str, object]
    ) -> tuple[tuple[CatalogSnapshot, ...], int]: ...
    async def citations(self, ref: EntityRef) -> tuple[Citation, ...]: ...
    async def get(self, ref: EntityRef) -> CatalogSnapshot: ...
    async def create(self, prepared: PreparedCatalog) -> CatalogSnapshot: ...
    async def replace(
        self, ref: EntityRef, prepared: PreparedCatalog, expected_version: int
    ) -> CatalogSnapshot: ...
    async def delete(
        self, ref: EntityRef, expected_version: int, *, include_reviews: bool = False
    ) -> tuple[str, ...]: ...
