"""Explicit local indexing/search entry point; selects DB via process environment."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.application.recommendations.contracts import (
    text_retrieval_adapter,
)
from food_recommender.domain.values import Category
from food_recommender.infrastructure.embeddings.minilm import MiniLMEncoder
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.indexing.text import TextIndexer
from food_recommender.infrastructure.persistence.search.text import PostgresTextSearch
from food_recommender.retrieval.models import TextPlan
from food_recommender.retrieval.service import TextRetrieval


async def execute(args: argparse.Namespace) -> int:
    encoder = await asyncio.to_thread(MiniLMEncoder, args.model_root)
    engine = create_database_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        if args.command == "index":
            result = await TextIndexer(sessions, encoder).build()
            print(json.dumps(result, sort_keys=True))
            return 0
        plan = TextPlan(
            args.query,
            categories=tuple(Category(c) for c in args.category),
            sources=tuple(args.source),
            cuisine=args.cuisine,
            location=args.location,
            max_price_band=args.max_price_band,
            name=args.name,
            demo_profile_id=args.demo_profile_id,
            limit=args.limit,
        )
        outcome = await TextRetrieval(PostgresTextSearch(sessions), encoder).run(plan)
        print(text_retrieval_adapter.dump_json(outcome, indent=2).decode())
        return 0 if outcome.status in ("success", "no_results") else 2
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument(
        "--category",
        nargs="+",
        choices=("restaurant", "recipe"),
        default=["restaurant", "recipe"],
    )
    search.add_argument(
        "--source",
        nargs="+",
        choices=("restaurant", "recipe", "review"),
        default=["restaurant", "recipe"],
    )
    search.add_argument("--cuisine")
    search.add_argument("--location")
    search.add_argument("--max-price-band", type=int)
    search.add_argument("--name")
    search.add_argument("--demo-profile-id")
    search.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    try:
        code = asyncio.run(execute(args))
    except (OSError, ValueError, RuntimeError, KeyError):
        print(
            json.dumps(
                {
                    "status": "dependency_error",
                    "error_code": "setup_or_index_unavailable",
                }
            )
        )
        code = 2
    raise SystemExit(code)


if __name__ == "__main__":
    main()
