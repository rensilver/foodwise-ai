"""Shared read-only catalog lookups with explicit ambiguity and scope."""

from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, model_validator


class RestaurantMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    source_id: str
    source_record_id: str | None = None
    description: str | None = None
    cuisine: str | None = None
    location: str | None = None
    price_band: int | None = None
    vibe: str | None = None
    environment: str | None = None


class ReviewMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    restaurant_id: str
    source_id: str
    source_record_id: str
    text: str
    published_on: date | None = None
    limitation: str = "Synthetic course review; not a verified customer review"


class LookupResult[T](BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["matched", "ambiguous", "no_match"]
    matches: tuple[T, ...]

    @model_validator(mode="after")
    def coherent(self) -> "LookupResult[T]":
        if (self.status == "no_match") != (not self.matches) or (
            self.status == "ambiguous" and len(self.matches) < 2
        ):
            raise ValueError("Incoherent lookup outcome")
        return self


class LookupStore(Protocol):
    async def restaurants(self, name: str) -> tuple[RestaurantMatch, ...]: ...
    async def vibes(self, vibe: str, limit: int) -> tuple[RestaurantMatch, ...]: ...
    async def reviews(
        self, restaurant_id: str, profile: str
    ) -> tuple[ReviewMatch, ...]: ...


class LookupService:
    def __init__(self, store: LookupStore) -> None:
        self.store = store

    async def restaurant(self, name: str) -> LookupResult[RestaurantMatch]:
        self._validate(name)
        matches = await self.store.restaurants(name)
        return LookupResult(
            status="ambiguous"
            if len(matches) > 1
            else "matched"
            if matches
            else "no_match",
            matches=matches,
        )

    async def vibe(self, vibe: str, limit: int = 20) -> LookupResult[RestaurantMatch]:
        self._validate(vibe)
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Invalid limit")
        matches = await self.store.vibes(vibe, limit)
        return LookupResult(
            status="matched" if matches else "no_match", matches=matches
        )

    async def review(
        self, restaurant_id: str, profile: str
    ) -> LookupResult[ReviewMatch]:
        self._validate(restaurant_id)
        self._validate(profile)
        matches = await self.store.reviews(restaurant_id, profile)
        return LookupResult(
            status="matched" if matches else "no_match", matches=matches
        )

    @staticmethod
    def _validate(value: str) -> None:
        if not value.strip() or len(value) > 200:
            raise ValueError("Invalid lookup")
