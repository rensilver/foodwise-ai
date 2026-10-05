"""Dated evidence values and trend-cache persistence contract."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class TrendItem:
    id: UUID
    url: str
    excerpt: str
    published_on: date | None
    retrieved_at: datetime


@dataclass(frozen=True)
class CachedTrends:
    query_hash: str
    query: str
    retrieved_at: datetime
    expires_at: datetime
    evidence: tuple[TrendItem, ...]


class TrendRepository(Protocol):
    async def get(self, query_hash: str, now: datetime) -> CachedTrends | None: ...
    async def put(self, result: CachedTrends) -> None: ...
