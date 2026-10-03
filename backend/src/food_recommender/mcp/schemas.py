"""Bounded MCP request schemas; no paths, SQL, URLs or provider configuration."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import Category
from food_recommender.retrieval.models import TextPlan


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    query: str = Field(min_length=1, max_length=2000)
    cuisine: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    max_price_band: int | None = Field(default=None, ge=1, le=4, strict=True)
    entity_ids: tuple[str, ...] = Field(default=(), max_length=20)
    constraints: tuple[Constraint, ...] = Field(default=(), max_length=20)
    demo_profile_id: str | None = Field(default=None, min_length=1, max_length=200)
    include_reviews: bool = False
    limit: int = Field(default=20, ge=1, le=20, strict=True)

    @field_validator("entity_ids")
    @classmethod
    def bounded_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not v.strip() or len(v) > 200 for v in values):
            raise ValueError("Invalid entity ID")
        return values

    def plan(self, category: Category) -> TextPlan:
        source: Literal["restaurant", "recipe"] = (
            "restaurant" if category == Category.RESTAURANT else "recipe"
        )
        sources: tuple[Literal["restaurant", "recipe", "review"], ...] = (
            (source, "review")
            if self.include_reviews and category == Category.RESTAURANT
            else (source,)
        )
        return TextPlan(
            query=self.query,
            categories=(category,),
            sources=sources,
            cuisine=self.cuisine,
            location=self.location if category == Category.RESTAURANT else None,
            max_price_band=self.max_price_band
            if category == Category.RESTAURANT
            else None,
            entity_ids=self.entity_ids,
            demo_profile_id=self.demo_profile_id,
            constraints=self.constraints,
            limit=self.limit,
        )


class ImageRequest(SearchRequest):
    category: Category = Category.RECIPE
    media_id: str | None = Field(
        default=None, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    session_id: UUID | None = None


# Reuse the domain constraint schema, including explicit hard-constraint provenance.
constraint_adapter = TypeAdapter(tuple[Constraint, ...])
