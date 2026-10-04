"""Real stdio and Streamable HTTP over the disposable PostgreSQL schema."""

import asyncio
import os
import socket
import sys
from uuid import uuid4

import pytest
import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from sqlalchemy.engine import make_url

from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.mcp.server import create_app

EXPECTED = {
    "get_restaurant_info",
    "recommend_by_vibe",
    "get_review",
    "search_restaurants",
    "search_recipes",
    "search_images",
    "search_food_trends",
}


async def exercise(client):
    async with client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == EXPECTED
        assert all(tool.annotations.read_only_hint for tool in tools)
        assert len(await client.list_resources()) == 3
        missing = await client.call_tool(
            "get_restaurant_info", {"name": "x'; DROP TABLE restaurants; --"}
        )
        assert missing.structured_content["status"] == "no_match"
        for name, arguments in (
            ("delete_restaurant", {}),
            ("execute_sql", {"sql": "SELECT 1"}),
            ("search_recipes", {"request": {"query": "food", "limit": 21}}),
            ("search_images", {"request": {"query": "food", "path": "/etc/passwd"}}),
            ("get_review", {"restaurant_id": "1"}),
        ):
            result = await client.call_tool(name, arguments, raise_on_error=False)
            assert result.is_error
        with pytest.raises(Exception):
            await client.read_resource("file:///etc/passwd")
        trends = await client.call_tool(
            "search_food_trends",
            {"request": {"concepts": ["fermentation"], "run_id": str(uuid4())}},
        )
        assert trends.structured_content["reason"] == "missing_credentials"
        result = await client.call_tool(
            "search_recipes", {"request": {"query": "food"}}
        )
        assert result.structured_content["status"] == "dependency_error"
        await client.read_resource("foodwise://source-provenance")
        assert {tool.name for tool in await client.list_tools()} == EXPECTED


@pytest.mark.asyncio
async def test_stdio_protocol(database_url, tmp_path):
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "food_recommender.mcp.server"],
        env={
            "DATABASE_URL": make_url(database_url)
            .set(drivername="postgresql+psycopg")
            .render_as_string(hide_password=False),
            "MEDIA_ROOT": str(tmp_path),
            "TAVILY_API_KEY": "",
            "MINILM_ROOT": "",
            "CLIP_ROOT": "",
        },
        cwd=os.getcwd(),
    )
    # Unset optional model roots rather than treating empty paths as provisioned models.
    transport.env.pop("MINILM_ROOT")
    transport.env.pop("CLIP_ROOT")
    await exercise(Client(transport, timeout=10))


@pytest.mark.asyncio
async def test_streamable_http_protocol(database_url, tmp_path):
    settings = MCPSettings(
        DATABASE_URL=make_url(database_url)
        .set(drivername="postgresql+psycopg")
        .render_as_string(hide_password=False),
        MEDIA_ROOT=tmp_path,
        TAVILY_API_KEY="",
        MINILM_ROOT=None,
        CLIP_ROOT=None,
    )
    app = create_app(settings)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        config = uvicorn.Config(app, log_config=None, access_log=False)
        server = uvicorn.Server(config)
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.02)
            # Security permits the configured Compose/host authority; socket port is dynamic.
            from fastmcp.client.transports import StreamableHttpTransport

            await exercise(
                Client(
                    StreamableHttpTransport(
                        f"http://127.0.0.1:{port}/mcp",
                        headers={"Host": "127.0.0.1:8001"},
                    ),
                    timeout=10,
                )
            )
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=10)
