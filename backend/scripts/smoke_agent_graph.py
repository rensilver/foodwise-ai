"""Opt-in six-role graph over real stdio MCP, PostgreSQL/pgvector, Groq and Tavily."""

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
from check_groq_capabilities import ProbeSettings
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.agents.graph import build_graph
from food_recommender.agents.runner import GraphRunner
from food_recommender.application.workflow import TurnRequest
from food_recommender.composition import build_workflow_roles
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.observability import configure_logging
from food_recommender.infrastructure.persistence.checkpoints import (
    checkpoint_saver,
    setup_checkpoints,
)
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.runs import PostgresConversationRuns
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.infrastructure.providers.groq import GroqStructuredInference
from food_recommender.mcp.client import AgentMCP

SEED_QUERY = "Recommend Italian recipes featuring tomato and basil, such as pizza."


class RecordingTools:
    def __init__(self, gateway):
        self.gateway = gateway
        self.results = []

    async def call(self, name, arguments):
        result = await self.gateway.call(name, arguments)
        if name == "search_food_trends":
            self.results.append(result.model_dump(mode="json"))
        return result


async def smoke(provider_settings, mcp_settings):
    dsn = mcp_settings.database_url.get_secret_value().replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    engine = create_database_engine(dsn)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, conversation, run_id = uuid4(), uuid4(), uuid4()
    await setup_checkpoints(dsn)
    async with PostgresUnitOfWork(sessions) as uow:
        await uow.conversations.create_session(
            owner, hashlib.sha256(uuid4().bytes).hexdigest()
        )
        await uow.conversations.create(owner, conversation)
        await uow.commit()
    environment = {
        "DATABASE_URL": dsn,
        "MEDIA_ROOT": str(mcp_settings.media_root),
        "MINILM_ROOT": str(mcp_settings.minilm_root),
        "CLIP_ROOT": str(mcp_settings.clip_root),
        "TAVILY_API_KEY": mcp_settings.tavily_api_key.get_secret_value()
        if mcp_settings.tavily_api_key
        else "",
    }
    client = Client(
        StdioTransport(
            sys.executable, ["-m", "food_recommender.mcp.server"], env=environment
        ),
        timeout=30,
    )
    provider = None
    trend_tools = None
    try:
        async with (
            httpx.AsyncClient(follow_redirects=False) as http,
            checkpoint_saver(dsn) as saver,
            AgentMCP(client, "rag", session_id=owner) as rag,
            AgentMCP(client, "trend", run_id=run_id) as trend,
        ):
            provider = GroqStructuredInference(
                http, provider_settings.GROQ_API_KEY, provider_settings.GROQ_MODEL
            )
            trend_tools = RecordingTools(trend)
            roles = build_workflow_roles(provider, rag, trend_tools)
            runner = GraphRunner(
                build_graph(roles, checkpointer=saver),
                PostgresConversationRuns(engine),
                new_id=lambda: run_id,
            )
            result = await runner.run(
                owner,
                conversation,
                TurnRequest(
                    message=SEED_QUERY,
                    categories=["recipe"],
                    explicit={"cuisines": ["Italian"]},
                ),
            )
            saved = await runner.read(owner, conversation)
        final = result.get("final") or {}
        items = final.get("result", {}).get("recommendations", [])
        stage_names = {
            stage["stage"] for stage in result.get("metrics", {}).get("stages", [])
        }
        evidence = [c["evidence"] for c in result.get("catalog", [])]
        allowed = {
            c["entity"]["id"]: {citation["id"] for citation in c["citations"]}
            for c in evidence
        }
        validated = all(
            item["entity"]["id"] in allowed
            and set(item["citation_ids"]) <= allowed[item["entity"]["id"]]
            for item in items
        )
        return {
            "verified_at": datetime.now(UTC).isoformat(),
            "enabled_explicitly": True,
            "seed_query": SEED_QUERY,
            "model": provider_settings.GROQ_MODEL,
            "transport": "stdio MCP subprocess with real PostgreSQL exact pgvector/MiniLM retrieval",
            "limits": {
                "run_seconds": 120,
                "call_seconds": 30,
                "groq_concurrency": 3,
                "transport_retries": 2,
                "schema_repairs": 2,
                "synthesis_repairs": 1,
                "retrieval_attempts": 3,
                "trend_searches": 2,
            },
            "metrics": result.get("metrics"),
            "provider_usage": provider.usage,
            "candidate_count": len(evidence),
            "retrieved_ids": [c["entity"] for c in evidence],
            "profile_outcome": result.get("profile_outcome"),
            "branch_outcomes": {
                key: result.get(key) for key in ("trend", "style", "nutrition")
            },
            "trend_search_outcomes": trend_tools.results,
            "final": final,
            "catalog_citations": [
                citation for c in evidence for citation in c["citations"]
            ],
            "checkpoint_completed": saved.get("lifecycle") == "completed",
            "reference_validation_passed": validated,
            "passed": bool(
                items
                and validated
                and final.get("status") == "success"
                and stage_names
                == {
                    "profile",
                    "retrieval",
                    "trend",
                    "style",
                    "nutrition",
                    "recommendation",
                }
                and saved.get("lifecycle") == "completed"
            ),
            "limitations": [
                "One seed query demonstrates integration, not recommendation quality",
                "Unavailable or irrelevant live trend evidence does not produce trend claims",
            ],
        }
    finally:
        async with PostgresUnitOfWork(sessions) as uow:
            await uow.conversations.delete(owner, conversation)
            from sqlalchemy import delete

            from food_recommender.infrastructure.persistence.models.context import (
                BrowserSession,
            )

            await uow.session.execute(
                delete(BrowserSession).where(BrowserSession.id == owner)
            )
            await uow.commit()
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enable-live",
        action="store_true",
        help="Permit paid Groq and at most two Tavily requests under the 120-second run budget",
    )
    parser.add_argument("--env-file", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.enable_live:
        parser.error("Live calls require --enable-live")
    configure_logging()
    try:
        report = asyncio.run(
            smoke(
                ProbeSettings(_env_file=tuple(args.env_file)),
                MCPSettings(_env_file=tuple(args.env_file)),
            )
        )
    except Exception:
        print(
            "Graph smoke failed; check local catalog, checkpoints, models and fresh credentials. Diagnostics redacted."
        )
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "candidate_count": report["candidate_count"],
                "metrics": report["metrics"],
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
