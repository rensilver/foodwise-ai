"""Validated plans and unnormalized document branch scores."""

from dataclasses import dataclass
from typing import Literal

from food_recommender.domain.evidence import Citation
from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import Category, EntityRef, nonempty, unique


@dataclass(frozen=True)
class TextPlan:
    query: str
    categories: tuple[Category, ...] = (Category.RESTAURANT, Category.RECIPE)
    sources: tuple[Literal["restaurant", "recipe", "review"], ...] = (
        "restaurant",
        "recipe",
    )
    cuisine: str | None = None
    location: str | None = None
    max_price_band: int | None = None
    name: str | None = None
    entity_ids: tuple[str, ...] = ()
    demo_profile_id: str | None = None
    constraints: tuple[Constraint, ...] = ()
    limit: int = 20

    def __post_init__(self) -> None:
        nonempty(self.query)
        if (
            len(self.query) > 2000
            or type(self.limit) is not int
            or not 1 <= self.limit <= 20
        ):
            raise ValueError("Query/limit outside supported bounds")
        unique(self.categories)
        unique(self.sources)
        unique(self.entity_ids)
        if not self.categories or any(
            c not in (Category.RESTAURANT, Category.RECIPE) for c in self.categories
        ):
            raise ValueError("Unsupported category")
        if not self.sources or any(
            s not in ("restaurant", "recipe", "review") for s in self.sources
        ):
            raise ValueError("Unsupported source")
        if "review" in self.sources and self.demo_profile_id is None:
            raise ValueError("Review retrieval requires explicit demo-profile scope")
        for value in (
            self.cuisine,
            self.location,
            self.name,
            self.demo_profile_id,
            *self.entity_ids,
        ):
            if value is not None:
                nonempty(value)
        if self.max_price_band is not None and (
            type(self.max_price_band) is not int or not 1 <= self.max_price_band <= 4
        ):
            raise ValueError("Invalid price band")


@dataclass(frozen=True)
class TextHit:
    entity: EntityRef
    name: str
    citation: Citation
    lexical_score: float | None
    cosine_similarity: float | None
    ingredients: tuple[str, ...] | None
    allergens: tuple[str, ...] | None
    source_type: Literal["restaurant", "recipe", "review"]


@dataclass(frozen=True)
class ImageHit:
    entity: EntityRef
    name: str
    citation: Citation
    media_id: str
    cosine_similarity: float
    ingredients: tuple[str, ...] | None
    allergens: tuple[str, ...] | None
