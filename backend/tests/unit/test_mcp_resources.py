from unittest.mock import AsyncMock

import pytest
from fastmcp import Client, FastMCP

from food_recommender.mcp.resources import register_resources


@pytest.mark.asyncio
async def test_only_fixed_public_resources_are_exposed():
    store = AsyncMock()
    store.read.return_value = '{"catalog": "synthetic"}'
    server = FastMCP("test")
    register_resources(server, store)
    async with Client(server) as client:
        resources = await client.list_resources()
        assert {str(r.uri) for r in resources} == {
            "foodwise://culinary-map",
            "foodwise://dataset-manifest",
            "foodwise://source-provenance",
        }
        await client.read_resource("foodwise://source-provenance")
        store.read.assert_awaited_once_with("source-provenance")
        with pytest.raises(Exception):
            await client.read_resource("file:///etc/passwd")
