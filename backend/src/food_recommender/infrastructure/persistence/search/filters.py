"""Shared SQL metadata filters for text and image candidate selection."""

from typing import Any

from sqlalchemy import func
from sqlalchemy.sql import Select

from food_recommender.domain.values import Category
from food_recommender.infrastructure.persistence.models.catalog import (
    Recipe,
    Restaurant,
)
from food_recommender.retrieval.models import TextPlan


def normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def metadata_filters(
    statement: Select[Any], plan: TextPlan, category: Category
) -> Select[Any]:
    entity = Restaurant if category == Category.RESTAURANT else Recipe
    if category == Category.RESTAURANT:
        if plan.location is not None:
            statement = statement.where(
                Restaurant.normalized_location == normalize(plan.location)
            )
        if plan.max_price_band is not None:
            statement = statement.where(Restaurant.price_band <= plan.max_price_band)
    if plan.cuisine is not None:
        statement = statement.where(
            entity.normalized_cuisine == normalize(plan.cuisine)
        )
    if plan.name is not None:
        statement = statement.where(func.lower(entity.name) == normalize(plan.name))
    if plan.entity_ids:
        statement = statement.where(entity.id.in_(plan.entity_ids))
    return statement
