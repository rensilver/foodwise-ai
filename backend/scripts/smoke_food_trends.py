"""Explicit opt-in dated Tavily smoke through MCP and the real PostgreSQL cache."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastmcp import Client

from food_recommender.application.trends import trend_citations
from food_recommender.composition import build_mcp_services
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.tavily import TavilySearch
from food_recommender.mcp.client import AgentMCP
from food_recommender.mcp.server import create_server


async def smoke(settings: MCPSettings) -> dict[str, object]:
    services = build_mcp_services(settings)
    assert services.trends is not None
    provider = services.trends.provider
    if not isinstance(provider, TavilySearch):
        raise ValueError("Fresh Tavily key required in the selected environment")
    server = create_server(settings, services=services)
    outcomes = []
    citations = []
    async with AgentMCP(Client(server), "trend", run_id=uuid4()) as gateway:
        # Public concepts only; at most two live requests in this explicitly enabled run.
        for concepts in (("seasonal cooking",), ("fermentation", "regional cuisine")):
            result = await gateway.call(
                "search_food_trends",
                {"request": {"concepts": list(concepts), "geography": "global"}},
            )
            outcomes.append(result.model_dump(mode="json"))
            citations.extend(trend_citations(result, datetime.now(UTC)))
            if citations and provider.request_usage:
                break
    now = datetime.now(UTC)
    return {
        "verified_at": now.isoformat(),
        "enabled_explicitly": True,
        "transport": "MCP in-process; both wire transports verified separately",
        "provider": "Tavily news/basic",
        "limits": {
            "searches_per_run": 2,
            "results_per_search": 5,
            "window_days": 90,
            "cache_ttl_hours": 24,
        },
        "provider_requests": provider.request_usage,
        "outcomes": outcomes,
        "dated_citations": [
            dict(
                id=c.id,
                url=c.url,
                excerpt=c.excerpt,
                published_on=str(c.published_on),
                retrieved_at=c.retrieved_at.isoformat() if c.retrieved_at else None,
            )
            for c in citations
        ],
        "passed": bool(citations and provider.request_usage),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enable-live",
        action="store_true",
        help="Explicitly permit up to two paid Tavily requests",
    )
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.enable_live:
        parser.error("Live calls require --enable-live")
    try:
        settings = MCPSettings(_env_file=args.env_file)
        report = asyncio.run(smoke(settings))
    except Exception:
        print(
            "Live smoke failed: check local database, fresh Tavily credentials and MCP configuration; details redacted"
        )
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "provider_requests": len(report["provider_requests"]),
                "dated_citations": len(report["dated_citations"]),
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
