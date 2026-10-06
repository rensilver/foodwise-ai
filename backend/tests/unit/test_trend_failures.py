import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from food_recommender.application.trends.service import TrendRequest, TrendService
from food_recommender.infrastructure.providers.tavily import TavilySearch


@pytest.mark.parametrize(
    "status,reason",
    [(429, "rate_limited"), (500, "provider_error"), (401, "provider_error")],
)
@pytest.mark.asyncio
async def test_provider_errors_are_typed_and_bounded(status, reason):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(
            status, headers={"Retry-After": "0"}, text="private provider details"
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        service = TrendService(
            TavilySearch(SecretStr("synthetic-fixture-token"), http), sleep=AsyncMock()
        )
        result = await service.search(
            TrendRequest(concepts=("fermentation",), run_id=uuid4())
        )
    assert result.status == "unavailable" and result.reason == reason
    assert 1 <= len(requests) <= 2 and result.search_calls == len(requests)
    assert "private provider" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_timeout_missing_credentials_cache_failure_and_cancellation():
    request = TrendRequest(concepts=("fermentation",), run_id=uuid4())
    assert (await TrendService(None).search(request)).reason == "missing_credentials"
    provider = AsyncMock()
    provider.search.side_effect = TimeoutError()
    assert (
        await TrendService(provider, sleep=AsyncMock()).search(request)
    ).reason == "timeout"
    transaction = AsyncMock()
    transaction.__aenter__.side_effect = RuntimeError("private database error")
    assert (
        await TrendService(provider, lambda: transaction).search(request)
    ).reason == "cache_error"
    provider.search.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await TrendService(provider).search(request)


@pytest.mark.asyncio
async def test_retry_after_is_honored_without_exceeding_budget():
    sleep = AsyncMock()
    calls = 0

    def respond(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await TrendService(
            TavilySearch(SecretStr("synthetic-fixture-token"), http), sleep=sleep
        ).search(TrendRequest(concepts=("fermentation",), run_id=uuid4()))
    assert result.reason == "no_results" and result.search_calls == 2
    assert sleep.call_args.args[0] >= 2


@pytest.mark.asyncio
async def test_search_requests_explicit_publication_window():
    import json
    from datetime import UTC, datetime

    payloads = []

    def respond(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        await TavilySearch(
            SecretStr("synthetic-fixture-token"),
            http,
            clock=lambda: datetime(2026, 10, 6, tzinfo=UTC),
        ).search("food trends Korean cuisine California", max_results=5, days=90)
    assert payloads[0]["start_date"] == "2026-07-08"
    assert payloads[0]["end_date"] == "2026-10-06"
    assert payloads[0]["filter_by_published_date"] is True
    assert payloads[0]["include_published_date"] is True
    assert "days" not in payloads[0]
