"""Validated legacy adapters. Raw payloads survive normalization unchanged."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from food_recommender.domain.catalog import RecipeData, RestaurantData

INGESTION_VERSION = "3.1"


class SourceError(ValueError):
    def __init__(self, source: str, record_id: object, reason: str) -> None:
        self.source = source
        self.record_id = str(record_id)
        self.reason = reason
        super().__init__(f"{source} record {record_id}: {reason}")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def normalize(value: str | None) -> str | None:
    return None if value is None else " ".join(value.casefold().split())


def duration(value: str | None) -> str | None:
    if value is None:
        return None
    match = re.fullmatch(
        r"\s*(?:(\d+)\s*(?:hours?|hrs?))?\s*(?:(\d+)\s*(?:minutes?|mins?))?\s*", value
    )
    if match is None or not any(match.groups()):
        raise ValueError("Unsupported recipe duration")
    minutes = int(match[1] or 0) * 60 + int(match[2] or 0)
    if minutes > 10080:
        raise ValueError("Recipe duration exceeds seven days")
    return f"PT{minutes}M"


class Legacy(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    name: str = Field(min_length=1, pattern=r"\S")


class LegacyRestaurant(Legacy):
    itemId: int = Field(gt=0)
    food_style: str | None = None
    location: str | None = None
    type: str | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    price_range: int | None = Field(default=None, ge=1, le=4)
    signatures: list[str] | None = None
    vibe: str | None = None
    environment: str | None = None
    shortcomings: list[str] | None = None


class LegacyRecipe(Legacy):
    id: int = Field(gt=0)
    cuisine: str | None = None
    servings: int | None = Field(default=None, gt=0)
    prep_time: str | None = None
    cook_time: str | None = None
    total_time: str | None = None
    ingredients: list[str] | None = None
    directions: list[str] | None = None


class LegacyReview(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow", hide_input_in_errors=True)
    reviewId: int = Field(gt=0)
    itemId: int = Field(gt=0)
    userId: str = Field(min_length=1, pattern=r"\S")
    title: str | None = None
    text: str = Field(min_length=1, pattern=r"\S")
    rating: float | None = Field(default=None, ge=0, le=5)
    date: str | None = None
    language: str | None = None


@dataclass(frozen=True, kw_only=True)
class ReviewData:
    id: str
    source_id: str
    source_record_id: str
    restaurant_id: str
    demo_profile_id: str
    title: str | None
    text: str
    rating: float | None
    published_on: date | None
    language: str | None


type SeedData = RestaurantData | RecipeData | ReviewData


@dataclass(frozen=True)
class AdaptedRecord:
    data: SeedData
    raw: dict[str, Any]
    locator: str


def adapt_restaurant(raw: dict[str, Any], source: str) -> AdaptedRecord:
    try:
        item = LegacyRestaurant.model_validate(raw)
        data = RestaurantData(
            id=str(item.itemId),
            source_id="course-restaurants",
            source_record_id=str(item.itemId),
            name=item.name,
            cuisine=item.food_style,
            normalized_cuisine=normalize(item.food_style),
            location=item.location,
            normalized_location=normalize(item.location),
            restaurant_type=item.type,
            rating=item.rating,
            price_band=item.price_range,
            signatures=None if item.signatures is None else tuple(item.signatures),
            vibe=item.vibe,
            environment=item.environment,
            shortcomings=None
            if item.shortcomings is None
            else tuple(item.shortcomings),
        )
        return AdaptedRecord(data, dict(raw), source)
    except (ValidationError, ValueError):
        raise SourceError(
            source, raw.get("itemId", "?"), "Invalid restaurant fields"
        ) from None


def adapt_recipe(raw: dict[str, Any], source: str) -> AdaptedRecord:
    try:
        item = LegacyRecipe.model_validate(raw)
        data = RecipeData(
            id=str(item.id),
            source_id="course-recipes",
            source_record_id=str(item.id),
            name=item.name,
            cuisine=item.cuisine,
            normalized_cuisine=normalize(item.cuisine),
            servings=item.servings,
            prep_time=duration(item.prep_time),
            cook_time=duration(item.cook_time),
            total_time=duration(item.total_time),
            ingredients=None if item.ingredients is None else tuple(item.ingredients),
            directions=None if item.directions is None else tuple(item.directions),
        )
        return AdaptedRecord(data, dict(raw), source)
    except (ValidationError, ValueError):
        raise SourceError(
            source, raw.get("id", "?"), "Invalid recipe fields or duration"
        ) from None


def adapt_review(raw: dict[str, Any], source: str) -> AdaptedRecord:
    try:
        item = LegacyReview.model_validate(raw)
        data = ReviewData(
            id=str(item.reviewId),
            source_id="course-reviews",
            source_record_id=str(item.reviewId),
            restaurant_id=str(item.itemId),
            demo_profile_id=item.userId,
            title=item.title,
            text=item.text,
            rating=item.rating,
            published_on=None if item.date is None else date.fromisoformat(item.date),
            language=item.language,
        )
        return AdaptedRecord(data, dict(raw), source)
    except (ValidationError, ValueError):
        raise SourceError(
            source, raw.get("reviewId", "?"), "Invalid review fields or date"
        ) from None
