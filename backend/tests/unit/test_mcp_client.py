from unittest.mock import AsyncMock

import pytest
from fastmcp import Client, FastMCP

from food_recommender.application.lookups import LookupService
from food_recommender.mcp.client import AgentMCP, ToolPolicyError
from food_recommender.mcp.tools import register_lookups


@pytest.mark.asyncio
async def test_discovery_allowlist_validation_and_reuse():
    store = AsyncMock()
    store.restaurants.return_value = ()
    server = FastMCP("test")
    register_lookups(server, LookupService(store))
    async with AgentMCP(Client(server), "rag") as gateway:
        assert (
            await gateway.call("get_restaurant_info", {"name": "missing"})
        ).status == "no_match"
        assert (
            await gateway.call("get_restaurant_info", {"name": "again"})
        ).status == "no_match"
        for name, args in (
            ("delete_restaurant", {}),
            ("get_restaurant_info", {"name": "a", "sql": "DROP"}),
            ("get_restaurant_info", {"name": "a", "server": "http://evil"}),
        ):
            with pytest.raises(ToolPolicyError):
                await gateway.call(name, args)
        assert store.restaurants.await_count == 2
    async with AgentMCP(Client(server), "style") as gateway:
        with pytest.raises(ToolPolicyError):
            await gateway.call("get_restaurant_info", {"name": "a"})


@pytest.mark.asyncio
async def test_invalid_results_and_changed_scope_cannot_escape_validation():
    from types import SimpleNamespace
    from unittest.mock import patch
    from uuid import uuid4

    store = AsyncMock()
    server = FastMCP("test")
    register_lookups(server, LookupService(store))
    async with AgentMCP(
        Client(server), "rag", demo_profile_id="demo-a", session_id=uuid4()
    ) as gateway:
        with pytest.raises(ToolPolicyError):
            await gateway.call(
                "get_review", {"restaurant_id": "1", "demo_profile_id": "demo-b"}
            )
        with patch.object(
            gateway.client,
            "call_tool",
            AsyncMock(
                return_value=SimpleNamespace(
                    is_error=False,
                    structured_content={
                        "status": "no_match",
                        "matches": [],
                        "secret": "untrusted",
                    },
                )
            ),
        ):
            with pytest.raises(ToolPolicyError, match="Invalid tool result"):
                await gateway.call("get_restaurant_info", {"name": "a"})
