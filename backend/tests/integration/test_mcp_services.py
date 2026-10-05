"""Shared MCP services against real transactional catalog and vectors."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastmcp import Client
from sqlalchemy import text
from test_ingestion_store import seed_store as seed_store
from test_text_search import populate

from food_recommender.application.catalog.lookups import LookupService
from food_recommender.application.services import Services
from food_recommender.application.trends.ports import TrendItem
from food_recommender.application.trends.service import TrendRequest, TrendService
from food_recommender.composition import build_multimodal_retrieval
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.persistence.repositories.lookups import (
    PostgresLookups,
)
from food_recommender.infrastructure.persistence.repositories.resources import (
    PostgresCatalogResources,
)
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.mcp.client import AgentMCP
from food_recommender.mcp.server import create_server


@pytest.mark.asyncio
async def test_real_lookup_filters_reviews_resources_and_rag_evidence(
    seed_store, tmp_path
):
    store, connection = seed_store
    _, encoder = await populate(store, tmp_path)
    await connection.execute(
        text("UPDATE restaurants SET name = 'Garden' WHERE id = '2'")
    )
    services = Services(
        readiness=AsyncMock(),
        lookups=LookupService(PostgresLookups(store.sessions)),
        retrieval=build_multimodal_retrieval(store.sessions, encoder, None, tmp_path),
        resources=PostgresCatalogResources(store.sessions),
    )
    server = create_server(
        MCPSettings(
            DATABASE_URL="postgresql://foodwise@localhost/foodwise", MEDIA_ROOT=tmp_path
        ),
        services=services,
    )
    async with AgentMCP(Client(server), "rag", demo_profile_id="demo-a") as client:
        lookup = await client.call("get_restaurant_info", {"name": "Garden"})
        assert lookup.status == "ambiguous" and {m.id for m in lookup.matches} == {
            "1",
            "2",
        }
        vibe = await client.call("recommend_by_vibe", {"vibe": "cozy", "limit": 1})
        assert vibe.status == "matched" and len(vibe.matches) == 1
        reviews = await client.call(
            "get_review", {"restaurant_id": "1", "demo_profile_id": "demo-a"}
        )
        assert {m.id for m in reviews.matches} == {"9"}
        result = await client.call(
            "search_recipes",
            {
                "request": {
                    "query": "pizza",
                    "cuisine": "Italian",
                    "location": "does not apply",
                    "limit": 1,
                }
            },
        )
        assert result.status == "success" and result.candidates[0].ingredients == (
            "cheese",
            "tomato",
        )
        assert result.candidates[0].evidence.citations[0].document_id
        resources = await client.client.read_resource("foodwise://source-provenance")
        assert (
            "demo-a" not in resources[0].text
            and '"record_type": "review"' not in resources[0].text
        )


@pytest.mark.asyncio
async def test_real_trend_cache_round_trip_and_no_repeated_search(seed_store):
    store, _ = seed_store
    now = datetime(2026, 10, 3, tzinfo=UTC)
    provider = AsyncMock()
    provider.search.return_value = (
        TrendItem(
            uuid4(), "https://example.org/news", "Dated food evidence", now.date(), now
        ),
    )
    service = TrendService(
        provider, lambda: PostgresUnitOfWork(store.sessions), clock=lambda: now
    )
    request = TrendRequest(concepts=("fermentation",), run_id=uuid4())
    first = await service.search(request)
    assert first.status == "available" and first.search_calls == 1
    cached = await service.search(request)
    assert cached.evidence == first.evidence and cached.cache_status == "hit"
    assert cached.search_calls == 0 and provider.search.await_count == 1
