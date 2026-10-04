"""Source-backed catalog reads over the shared repository transaction."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from food_recommender.application.ports import UnitOfWork
from food_recommender.domain.catalog import CatalogData
from food_recommender.domain.evidence import Citation
from food_recommender.domain.values import Category, EntityRef


class RecipeFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100000)
    cuisine: str | None = Field(default=None, min_length=1, max_length=100)
    q: str | None = Field(default=None, min_length=1, max_length=200)


class RestaurantFilters(RecipeFilters):
    location: str | None = Field(default=None, min_length=1, max_length=100)
    price_band: int | None = Field(default=None, ge=1, le=4)


@dataclass(frozen=True)
class CatalogDetail:
    data: CatalogData
    version: int
    citations: tuple[Citation, ...]
    synthetic: bool = True


@dataclass(frozen=True)
class CatalogPage:
    items: tuple[CatalogDetail, ...]
    total: int
    limit: int
    offset: int


class BrowseService:
    def __init__(self, transactions: Callable[[], UnitOfWork]) -> None:
        self.transactions = transactions

    async def detail(self, ref: EntityRef) -> CatalogDetail:
        async with self.transactions() as transaction:
            item = await transaction.catalog.get(ref)
            return CatalogDetail(
                item.data, item.version, await transaction.catalog.citations(ref)
            )

    async def list(self, category: Category, filters: RecipeFilters) -> CatalogPage:
        async with self.transactions() as transaction:
            items, total = await transaction.catalog.browse(
                category, filters.model_dump()
            )
            result = tuple(
                [
                    CatalogDetail(
                        item.data,
                        item.version,
                        await transaction.catalog.citations(
                            EntityRef(category, item.data.id)
                        ),
                    )
                    for item in items
                ]
            )
            return CatalogPage(result, total, filters.limit, filters.offset)
