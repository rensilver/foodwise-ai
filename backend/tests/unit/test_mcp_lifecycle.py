from unittest.mock import AsyncMock

import pytest
from fastmcp import Client

from food_recommender.application.services import Services
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.mcp.server import create_server


@pytest.mark.asyncio
async def test_connection_reuses_server_and_closes_dependencies_once():
    close = AsyncMock()
    settings = MCPSettings(
        DATABASE_URL="postgresql://foodwise@localhost/foodwise", MEDIA_ROOT="/tmp/media"
    )
    server = create_server(
        settings, services=Services(readiness=AsyncMock(), close=close)
    )
    async with Client(server) as client:
        assert await client.list_tools()
        assert await client.list_tools()
        close.assert_not_awaited()
    close.assert_awaited_once()
