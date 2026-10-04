"""Read-only catalog verification with real pretrained models over both MCP transports."""

import argparse
import asyncio
import json
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastmcp import Client
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.mcp.client import AgentMCP
from food_recommender.mcp.server import create_app


async def exercise(client):
    async with AgentMCP(client, "rag") as gateway:
        rows = {}
        for tool, query in (
            ("search_restaurants", "Italian San Francisco"),
            ("search_recipes", "pizza"),
            ("search_images", "pizza"),
        ):
            result = await gateway.call(tool, {"request": {"query": query, "limit": 3}})
            assert result.status == "success" and 0 < len(result.candidates) <= 3
            assert all(c.evidence.citations for c in result.candidates)
            rows[tool] = {
                "status": result.status,
                "ids": [c.evidence.entity.id for c in result.candidates],
                "category": result.candidates[0].evidence.entity.category.value,
                "citation_count": sum(
                    len(c.evidence.citations) for c in result.candidates
                ),
            }
        resources = await client.read_resource("foodwise://culinary-map")
        paragraphs = resources[0].text.split("\n\n")
        assert len(paragraphs) == 210
        rows["culinary_map_paragraphs"] = len(paragraphs)
        rows["discovered_tools"] = sorted(gateway.schemas)
        return rows


async def verify(settings):
    environment = {
        "DATABASE_URL": settings.database_url.get_secret_value(),
        "MEDIA_ROOT": str(settings.media_root),
        "TAVILY_API_KEY": "",
        "MINILM_ROOT": str(settings.minilm_root),
        "CLIP_ROOT": str(settings.clip_root),
    }
    stdio = await exercise(
        Client(
            StdioTransport(
                sys.executable, ["-m", "food_recommender.mcp.server"], env=environment
            ),
            timeout=30,
        )
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(create_app(settings), log_config=None, access_log=False)
        )
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(10):
                while not server.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.02)
            http = await exercise(
                Client(
                    StreamableHttpTransport(
                        f"http://127.0.0.1:{port}/mcp",
                        headers={"Host": "127.0.0.1:8001"},
                    ),
                    timeout=30,
                )
            )
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=10)
    assert http == stdio
    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "paid_calls": 0,
        "stdio": stdio,
        "streamable_http": http,
        "same_results": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        settings = MCPSettings(TAVILY_API_KEY="")
        if not settings.minilm_root or not settings.clip_root:
            raise ValueError("Provision both pretrained encoders explicitly")
        report = asyncio.run(verify(settings))
    except Exception:
        print(
            "Catalog MCP verification failed; check database/media/model provisioning. Details redacted."
        )
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Catalog verification passed over both transports; no paid calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
