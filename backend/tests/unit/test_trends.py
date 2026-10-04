from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from food_recommender.application.trends import TrendRequest, TrendService


@pytest.mark.asyncio
async def test_two_search_budget_and_five_result_provider_contract():
    provider = AsyncMock()
    provider.search.return_value = ()
    service = TrendService(provider, clock=lambda: datetime(2026, 10, 3, tzinfo=UTC))
    request = TrendRequest(concepts=("fermentation",), run_id=uuid4())
    assert (await service.search(request)).reason == "no_results"
    assert (await service.search(request)).reason == "no_results"
    assert (await service.search(request)).reason == "budget_exhausted"
    assert provider.search.await_count == 2
    provider.search.assert_awaited_with(
        "food trends fermentation California", max_results=5, days=90
    )
