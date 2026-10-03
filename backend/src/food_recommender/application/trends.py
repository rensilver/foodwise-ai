"""Bounded public culinary search and cache; provider data remains untrusted."""

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from food_recommender.application.ports import CachedTrends, TrendItem, UnitOfWork

Concept = Literal[
    "fermentation",
    "regional cuisine",
    "seasonal cooking",
    "street food",
    "comfort food",
    "whole grains",
    "sustainable cooking",
    "noodles",
    "sourdough",
    "Mediterranean cuisine",
    "Mexican cuisine",
    "Japanese cuisine",
    "Indian cuisine",
    "Korean cuisine",
    "Italian cuisine",
    "seafood",
    "barbecue",
    "desserts",
    "coffee",
    "tea",
]
Geography = Literal["California", "United States", "global"]


class TrendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    concepts: tuple[Concept, ...] = Field(min_length=1, max_length=3)
    geography: Geography = "California"
    run_id: UUID

    def query(self) -> str:
        return f"food trends {' '.join(sorted(set(self.concepts)))} {self.geography}"


class TrendResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["available", "unavailable"]
    evidence: tuple[TrendItem, ...] = Field(default=(), max_length=5)
    reason: (
        Literal[
            "no_results",
            "budget_exhausted",
            "missing_credentials",
            "timeout",
            "rate_limited",
            "provider_error",
            "cache_error",
            "stale_evidence",
        ]
        | None
    ) = None
    cache_status: Literal["hit", "miss"] = "miss"
    search_calls: int = Field(default=0, ge=0, le=2)
    limitation: str = (
        "Web excerpts are untrusted evidence; validate claims against dated excerpts"
    )


class TrendProvider(Protocol):
    async def search(
        self, query: str, *, max_results: int, days: int
    ) -> tuple[TrendItem, ...]: ...


class TrendService:
    def __init__(
        self,
        provider: TrendProvider | None,
        transactions: Callable[[], UnitOfWork] | None = None,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.provider, self.transactions, self.clock = provider, transactions, clock
        self.runs: dict[UUID, tuple[datetime, int]] = {}
        self.lock = asyncio.Lock()

    async def search(self, request: TrendRequest) -> TrendResult:
        now, query = self.clock(), request.query()
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        if self.transactions:
            async with self.transactions() as transaction:
                cached = await transaction.trends.get(query_hash, now)
            if cached is not None:
                return TrendResult(
                    status="available" if cached.evidence else "unavailable",
                    evidence=cached.evidence,
                    cache_status="hit",
                    reason=None if cached.evidence else "no_results",
                )
        if self.provider is None:
            return TrendResult(status="unavailable", reason="missing_credentials")
        async with self.lock:
            self.runs = {
                key: value
                for key, value in self.runs.items()
                if now - value[0] < timedelta(hours=24)
            }
            started, count = self.runs.get(request.run_id, (now, 0))
            if count >= 2 or (
                request.run_id not in self.runs and len(self.runs) >= 4096
            ):
                return TrendResult(status="unavailable", reason="budget_exhausted")
            self.runs[request.run_id] = (started, count + 1)
        async with asyncio.timeout(30):
            items = (await self.provider.search(query, max_results=5, days=90))[:5]
        if self.transactions:
            async with self.transactions() as transaction:
                await transaction.trends.put(
                    CachedTrends(
                        query_hash, query, now, now + timedelta(hours=24), items
                    )
                )
                await transaction.commit()
        return TrendResult(
            status="available" if items else "unavailable",
            evidence=items,
            reason=None if items else "no_results",
            search_calls=1,
        )
