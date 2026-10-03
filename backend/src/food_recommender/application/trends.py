"""Bounded public culinary search and cache; provider data remains untrusted."""

import asyncio
import hashlib
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from food_recommender.application.ports import CachedTrends, TrendItem, UnitOfWork
from food_recommender.domain.evidence import Citation, CitationKind

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
    excluded_count: int = Field(default=0, ge=0, le=5)

    @model_validator(mode="after")
    def coherent(self) -> "TrendResult":
        if (self.status == "available") != bool(self.evidence) or (
            self.status == "unavailable"
        ) != (self.reason is not None):
            raise ValueError("Incoherent trend outcome")
        return self

    limitation: str = (
        "Web excerpts are untrusted evidence; validate claims against dated excerpts"
    )


class TrendProvider(Protocol):
    async def search(
        self, query: str, *, max_results: int, days: int
    ) -> tuple[TrendItem, ...]: ...


class TrendProviderError(Exception):
    def __init__(
        self,
        reason: Literal["timeout", "rate_limited", "provider_error"],
        *,
        retryable: bool = False,
        retry_after: float = 0,
    ) -> None:
        super().__init__("Trend provider unavailable")
        self.reason, self.retryable, self.retry_after = reason, retryable, retry_after


@dataclass
class SearchUsage:
    calls: int = 0


class TrendService:
    def __init__(
        self,
        provider: TrendProvider | None,
        transactions: Callable[[], UnitOfWork] | None = None,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: random.uniform(0, 0.2),
    ) -> None:
        self.provider, self.transactions, self.clock = provider, transactions, clock
        self.sleep, self.jitter = sleep, jitter
        self.runs: dict[UUID, tuple[datetime, int]] = {}
        self.lock = asyncio.Lock()

    async def search(self, request: TrendRequest) -> TrendResult:
        usage = SearchUsage()
        try:
            async with asyncio.timeout(30):
                return await self._search(request, usage)
        except TimeoutError:
            return TrendResult(
                status="unavailable", reason="timeout", search_calls=usage.calls
            )

    async def _reserve(self, run_id: UUID) -> bool:
        now = self.clock()
        async with self.lock:
            self.runs = {
                key: value
                for key, value in self.runs.items()
                if now - value[0] < timedelta(hours=24)
            }
            started, count = self.runs.get(run_id, (now, 0))
            if count >= 2 or (run_id not in self.runs and len(self.runs) >= 4096):
                return False
            self.runs[run_id] = (started, count + 1)
            return True

    async def _search(self, request: TrendRequest, usage: SearchUsage) -> TrendResult:
        now, query = self.clock(), request.query()
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        if self.transactions:
            try:
                async with self.transactions() as transaction:
                    cached = await transaction.trends.get(query_hash, now)
            except Exception:
                return TrendResult(status="unavailable", reason="cache_error")
            if (
                cached is not None
                and cached.retrieved_at <= now < cached.expires_at
                and cached.expires_at - cached.retrieved_at <= timedelta(hours=24)
            ):
                fresh = tuple(
                    item for item in cached.evidence if current_evidence(item, now)
                )
                if fresh:
                    return TrendResult(
                        status="available",
                        evidence=fresh,
                        cache_status="hit",
                        excluded_count=len(cached.evidence) - len(fresh),
                    )
        if self.provider is None:
            return TrendResult(status="unavailable", reason="missing_credentials")
        last_error: TrendProviderError | None = None
        for attempt in range(3):
            if not await self._reserve(request.run_id):
                return TrendResult(
                    status="unavailable",
                    reason=last_error.reason if last_error else "budget_exhausted",
                    search_calls=usage.calls,
                )
            usage.calls += 1
            try:
                items = (await self.provider.search(query, max_results=5, days=90))[:5]
                break
            except TrendProviderError as error:
                last_error = error
            except TimeoutError:
                last_error = TrendProviderError("timeout", retryable=True)
            except Exception:
                last_error = TrendProviderError("provider_error")
            if (
                not last_error.retryable
                or attempt == 2
                or self.runs[request.run_id][1] >= 2
            ):
                return TrendResult(
                    status="unavailable",
                    reason=last_error.reason,
                    search_calls=usage.calls,
                )
            await self.sleep(
                max(last_error.retry_after, 0.25 * 2**attempt) + self.jitter()
            )
        else:
            return TrendResult(
                status="unavailable", reason="provider_error", search_calls=usage.calls
            )
        if self.transactions:
            try:
                async with self.transactions() as transaction:
                    await transaction.trends.put(
                        CachedTrends(
                            query_hash, query, now, now + timedelta(hours=24), items
                        )
                    )
                    await transaction.commit()
            except Exception:
                return TrendResult(
                    status="unavailable", reason="cache_error", search_calls=usage.calls
                )
        fresh = tuple(item for item in items if current_evidence(item, self.clock()))
        return TrendResult(
            status="available" if fresh else "unavailable",
            evidence=fresh,
            excluded_count=len(items) - len(fresh),
            reason=None if fresh else "stale_evidence" if items else "no_results",
            search_calls=usage.calls,
        )


def current_evidence(item: TrendItem, now: datetime) -> bool:
    """Publication establishes recency; retrieval establishes the cache lifetime."""
    return (
        now.utcoffset() is not None
        and item.retrieved_at.utcoffset() is not None
        and item.published_on is not None
        and now.date() - timedelta(days=90) <= item.published_on <= now.date()
        and item.retrieved_at <= now < item.retrieved_at + timedelta(hours=24)
    )


def trend_citations(result: TrendResult, now: datetime) -> tuple[Citation, ...]:
    """Revalidate immediately before synthesis/citation, including long-running turns."""
    return tuple(
        Citation(
            id=str(item.id),
            kind=CitationKind.WEB,
            source_id="tavily",
            excerpt=item.excerpt,
            url=item.url,
            published_on=item.published_on,
            retrieved_at=item.retrieved_at,
            attribution="source",
        )
        for item in result.evidence
        if current_evidence(item, now)
    )
