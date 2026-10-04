from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from food_recommender.application.ports import CachedTrends, TrendItem
from food_recommender.application.trends import (
    TrendRequest,
    TrendService,
    trend_citations,
)

NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)


def item(days, retrieved=NOW):
    return TrendItem(
        uuid4(),
        "https://example.org/food",
        "Food trend excerpt",
        None if days is None else (NOW - timedelta(days=days)).date(),
        retrieved,
    )


@pytest.mark.asyncio
async def test_unknown_stale_future_dates_do_not_support_current_claims():
    provider = AsyncMock()
    provider.search.return_value = (item(None), item(91), item(-1), item(1))
    service = TrendService(provider, clock=lambda: NOW)
    result = await service.search(
        TrendRequest(concepts=("fermentation",), run_id=uuid4())
    )
    assert result.status == "available" and len(result.evidence) == 1
    assert result.excluded_count == 3
    assert len(trend_citations(result, NOW)) == 1
    assert trend_citations(result, NOW + timedelta(hours=24)) == ()


@pytest.mark.asyncio
async def test_cache_read_revalidates_both_ttl_and_publication():
    transaction = AsyncMock()
    transaction.__aenter__.return_value = transaction
    transaction.trends.get.return_value = CachedTrends(
        "0" * 64,
        "food",
        NOW - timedelta(hours=1),
        NOW + timedelta(hours=23),
        (item(None), item(91)),
    )
    provider = AsyncMock()
    provider.search.return_value = (item(1),)
    service = TrendService(provider, lambda: transaction, clock=lambda: NOW)
    result = await service.search(
        TrendRequest(concepts=("fermentation",), run_id=uuid4())
    )
    assert result.cache_status == "miss" and result.status == "available"
    assert provider.search.await_count == 1
    stored = transaction.trends.put.call_args.args[0]
    assert stored.expires_at - stored.retrieved_at == timedelta(hours=24)


@pytest.mark.asyncio
async def test_unknown_dates_remain_stored_but_are_unavailable():
    transaction = AsyncMock()
    transaction.__aenter__.return_value = transaction
    transaction.trends.get.return_value = None
    provider = AsyncMock()
    provider.search.return_value = (item(None),)
    result = await TrendService(
        provider, lambda: transaction, clock=lambda: NOW
    ).search(TrendRequest(concepts=("fermentation",), run_id=uuid4()))
    assert result.reason == "stale_evidence" and result.evidence == ()
    assert transaction.trends.put.call_args.args[0].evidence[0].published_on is None
