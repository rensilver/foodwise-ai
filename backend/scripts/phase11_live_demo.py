"""Opt-in P11-04 graph demonstration; rejects degraded release evidence."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

ROLES = ("profile", "retrieval", "trend", "style", "nutrition", "recommendation")


def checks(state, *, image, today):
    stages = state.get("metrics", {}).get("stages", [])
    catalog = state.get("catalog", [])
    allowed = {
        (c["evidence"]["entity"]["category"], c["evidence"]["entity"]["id"]): {
            x["id"] for x in c["evidence"]["citations"]
        }
        for c in catalog
    }
    final = state.get("final") or {}
    items = final.get("result", {}).get("recommendations", [])
    claims = (state.get("trend") or {}).get("result", {}).get("claims", [])
    day = date.fromisoformat(today)
    dated = (
        bool(claims)
        and all(claim.get("citations") for claim in claims)
        and all(
            c.get("url", "").startswith("https://")
            and c.get("published_on")
            and 0 <= (day - date.fromisoformat(c["published_on"])).days <= 90
            and c.get("retrieved_at")
            for claim in claims
            for c in claim["citations"]
        )
    )
    return {
        "completed": state.get("lifecycle") == "completed",
        "six_successful_stages_once": len(stages) == 6
        and {s["stage"] for s in stages} == set(ROLES)
        and all(s["status"] == "success" for s in stages),
        "experts_available": all(
            (state.get(role) or {}).get("status") == "success"
            for role in ("trend", "style", "nutrition")
        ),
        "recommendations_present": bool(items) and final.get("status") == "success",
        "references_valid": bool(items)
        and all(
            (item["entity"]["category"], item["entity"]["id"]) in allowed
            and bool(item["citation_ids"])
            and set(item["citation_ids"])
            <= allowed[(item["entity"]["category"], item["entity"]["id"])]
            for item in items
        ),
        "dated_trend_claims": bool(dated),
        "real_text_scores": bool(catalog)
        and any(c.get("text_cosine_similarity") is not None for c in catalog),
        "real_image_scores": not image
        or any(c.get("image_cosine_similarity") is not None for c in catalog),
    }


class RecordingTools:
    def __init__(self, gateway):
        self.gateway, self.calls = gateway, []

    async def call(self, name, arguments):
        result = await self.gateway.call(name, arguments)
        from pydantic_core import to_jsonable_python

        self.calls.append({"tool": name, "result": to_jsonable_python(result)})
        return result


class TimedRole:
    def __init__(self, role, name, spans):
        self.role, self.name, self.spans = role, name, spans

    async def run(self, *args, **kwargs):
        span = {"stage": self.name, "start": time.monotonic()}
        self.spans.append(span)
        try:
            return await self.role.run(*args, **kwargs)
        finally:
            span["end"] = time.monotonic()


def order_checks(spans):
    by = {s["stage"]: s for s in spans}
    if set(by) != set(ROLES) or len(spans) != 6:
        return False
    experts = [by[n] for n in ("trend", "style", "nutrition")]
    return (
        by["profile"]["end"] <= by["retrieval"]["start"]
        and by["retrieval"]["end"] <= min(s["start"] for s in experts)
        and max(s["start"] for s in experts) < min(s["end"] for s in experts)
        and max(s["end"] for s in experts) <= by["recommendation"]["start"]
    )


async def demonstrate(args):
    from dataclasses import replace

    import httpx
    from check_openai_capabilities import ProbeSettings
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport
    from sqlalchemy import delete, select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from food_recommender.agents.graph import build_graph
    from food_recommender.agents.runner import GraphRunner
    from food_recommender.application.media.service import MediaService
    from food_recommender.application.recommendations.workflow import TurnRequest
    from food_recommender.composition import build_workflow_roles
    from food_recommender.infrastructure.mcp_config import MCPSettings
    from food_recommender.infrastructure.media.files import LocalMediaFiles
    from food_recommender.infrastructure.media.uploads import ImageSanitizer
    from food_recommender.infrastructure.persistence.checkpoints import checkpoint_saver
    from food_recommender.infrastructure.persistence.engine import (
        create_database_engine,
    )
    from food_recommender.infrastructure.persistence.models.context import (
        BrowserSession,
    )
    from food_recommender.infrastructure.persistence.models.provenance import (
        Media,
        SourceRecord,
    )
    from food_recommender.infrastructure.persistence.runs import (
        PostgresConversationRuns,
    )
    from food_recommender.infrastructure.persistence.unit_of_work import (
        PostgresUnitOfWork,
    )
    from food_recommender.infrastructure.providers.openai import (
        OpenAIStructuredInference,
    )
    from food_recommender.mcp.client import AgentMCP

    provider_settings = ProbeSettings(_env_file=args.env_file)
    settings = MCPSettings(_env_file=args.env_file)
    if not settings.tavily_api_key:
        raise ValueError("Live dated trends require Tavily")
    dsn = settings.database_url.get_secret_value().replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    engine = create_database_engine(dsn)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner, conversation = uuid4(), uuid4()
    files = LocalMediaFiles(settings.media_root)

    def transactions():
        return PostgresUnitOfWork(sessions)

    upload = None
    report = {
        "task": "P11-04",
        "verified_at": datetime.now(UTC).isoformat(),
        "model": provider_settings.OPENAI_MODEL,
        "transport": "real stdio MCP",
        "tracing_enabled": False,
        "turns": [],
        "passed": False,
    }
    root = Path(__file__).resolve().parents[2]
    report["runtime_hashes"] = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            root / "backend/src/food_recommender/agents/prompts.py",
            root / "backend/src/food_recommender/agents/nodes/profile.py",
            root
            / "backend/src/food_recommender/application/recommendations/profile_rules.py",
            root / "backend/src/food_recommender/agents/structured.py",
            root / "backend/src/food_recommender/agents/nodes/style.py",
            root / "backend/src/food_recommender/agents/nodes/trend.py",
            root / "backend/src/food_recommender/agents/nodes/recommendation.py",
            root / "backend/src/food_recommender/infrastructure/providers/tavily.py",
        )
    }
    async with transactions() as uow:
        await uow.conversations.create_session(
            owner, hashlib.sha256(uuid4().bytes).hexdigest()
        )
        await uow.conversations.create(owner, conversation)
        await uow.commit()
    try:
        async with sessions() as session:
            media = await session.scalar(
                select(Media)
                .join(SourceRecord, Media.source_record_id == SourceRecord.id)
                .where(SourceRecord.recipe_id == "20")
            )
            content = await files.read(media.storage_key)
        upload = await MediaService(transactions, files, ImageSanitizer()).upload(
            owner, content, "image/png"
        )
        environment = {
            "DATABASE_URL": dsn,
            "MEDIA_ROOT": str(settings.media_root),
            "MINILM_ROOT": str(settings.minilm_root),
            "CLIP_ROOT": str(settings.clip_root),
            "TAVILY_API_KEY": settings.tavily_api_key.get_secret_value(),
            "LANGFUSE_ENABLED": "false",
        }
        client = Client(
            StdioTransport(
                sys.executable, ["-m", "food_recommender.mcp.server"], env=environment
            ),
            timeout=30,
        )
        async with (
            httpx.AsyncClient(follow_redirects=False) as http,
            checkpoint_saver(dsn) as saver,
        ):
            provider = OpenAIStructuredInference(
                http, provider_settings.OPENAI_API_KEY, provider_settings.OPENAI_MODEL
            )
            turns = [
                TurnRequest(
                    message="Recommend a Korean restaurant in Fullerton.",
                    categories=["restaurant"],
                    explicit={"cuisines": ["Korean"], "location": "Fullerton"},
                ),
                TurnRequest(
                    message="Now recommend a Korean recipe like the food in this image.",
                    categories=["recipe"],
                    media_id=upload.id,
                ),
                TurnRequest(
                    message="I have a soy allergy. Only suggest a recipe if soy compliance is verified.",
                    categories=["recipe"],
                    explicit={
                        "constraints": [
                            {
                                "kind": "allergen",
                                "value": "soy",
                                "strength": "hard",
                                "origin": "explicit",
                            }
                        ]
                    },
                ),
            ]
            for number, request in enumerate(turns, 1):
                print(f"Running live turn {number}/3", flush=True)
                run = uuid4()
                async with (
                    AgentMCP(client, "rag", session_id=owner, run_id=run) as rag,
                    AgentMCP(client, "trend", run_id=run) as trend,
                ):
                    rag_tools, trend_tools = RecordingTools(rag), RecordingTools(trend)
                    roles = build_workflow_roles(provider, rag_tools, trend_tools)
                    spans = []
                    roles = replace(
                        roles,
                        **{n: TimedRole(getattr(roles, n), n, spans) for n in ROLES},
                    )
                    # Recreate the runner/graph every turn; only the PostgreSQL checkpoint supplies prior context.
                    runner = GraphRunner(
                        build_graph(roles, checkpointer=saver),
                        PostgresConversationRuns(engine),
                    )
                    result = await runner.run(owner, conversation, request, run_id=run)
                    saved = await runner.read(owner, conversation)
                positive = number < 3
                verification = (
                    checks(
                        result,
                        image=number == 2,
                        today=datetime.now(UTC).date().isoformat(),
                    )
                    if positive
                    else {
                        "no_unsafe_suggestions": not result.get("final", {})
                        .get("result", {})
                        .get("recommendations", []),
                        "hard_constraint_retained": any(
                            c["value"] == "soy" and c["strength"] == "hard"
                            for c in saved.get("profile", {})
                            .get("preferences", {})
                            .get("constraints", [])
                        ),
                        "retrieval_empty_under_restriction": result.get(
                            "retrieval", {}
                        ).get("status")
                        == "success"
                        and not result.get("catalog"),
                        "safe_completed_response": result.get("lifecycle")
                        == "completed"
                        and result.get("final", {}).get("status") == "success",
                    }
                )
                if positive:
                    verification["dependency_order_overlap_and_join"] = order_checks(
                        spans
                    )
                    verification["cuisine_retained"] = saved["profile"]["preferences"][
                        "cuisines"
                    ] == ["Korean"]
                    verification["checkpoint_roundtrip"] = (
                        saved["final"] == result["final"]
                        and saved["lifecycle"] == "completed"
                    )
                    if number == 2:
                        verification["image_search_called"] = any(
                            c["tool"] == "search_images" for c in rag_tools.calls
                        )
                        verification["actual_image_entity_found"] = any(
                            c["evidence"]["entity"]
                            == {"category": "recipe", "id": "20"}
                            and c.get("image_cosine_similarity") is not None
                            for c in result.get("catalog", [])
                        )
                row = {
                    "turn": number,
                    "message": request.message,
                    "checks": verification,
                    "metrics": result.get("metrics"),
                    "stage_spans_ms": [
                        {
                            "stage": span["stage"],
                            "start": round(
                                (span["start"] - spans[0]["start"]) * 1000, 3
                            ),
                            "end": round((span["end"] - spans[0]["start"]) * 1000, 3),
                        }
                        for span in spans
                    ],
                    "profile": saved.get("profile"),
                    "catalog": result.get("catalog"),
                    "trend": result.get("trend"),
                    "style": result.get("style"),
                    "nutrition": result.get("nutrition"),
                    "final": result.get("final"),
                    "tool_calls": rag_tools.calls + trend_tools.calls,
                }
                report["turns"].append(row)
                args.output.write_text(json.dumps(report, indent=2) + "\n")
                print(
                    json.dumps(
                        {
                            "turn": number,
                            "checks": verification,
                            "metrics": result.get("metrics"),
                        }
                    ),
                    flush=True,
                )
                if not all(verification.values()):
                    break
            report["provider_usage"] = provider.usage
            report["passed"] = len(report["turns"]) == 3 and all(
                all(t["checks"].values()) for t in report["turns"]
            )
    finally:
        async with transactions() as uow:
            await uow.conversations.delete(owner, conversation)
            if upload:
                await uow.session.execute(delete(Media).where(Media.id == upload.id))
            await uow.session.execute(
                delete(BrowserSession).where(BrowserSession.id == owner)
            )
            await uow.commit()
        if upload:
            await files.delete(upload.id + ".png")
        await engine.dispose()
        report["synthetic_context_removed"] = True
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--enable-live",
        action="store_true",
        help="Authorize up to three 120-second OpenAI runs and six bounded Tavily searches",
    )
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.enable_live:
        parser.error("Live provider calls require --enable-live")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Do not enable Cloud or inherited model downloads for this local demonstration.
    os.environ.update(
        LANGFUSE_ENABLED="false", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1"
    )
    try:
        report = asyncio.run(demonstrate(args))
    except Exception as error:
        report = (
            json.loads(args.output.read_text())
            if args.output.exists()
            else {"task": "P11-04"}
        )
        report.update(passed=False, failure_type=type(error).__name__)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print("Live demonstration failed; diagnostics redacted.", file=sys.stderr)
        return 2
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
