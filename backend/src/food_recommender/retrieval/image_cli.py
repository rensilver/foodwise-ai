"""Explicit offline image indexing; no inference on application startup."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.domain.values import Category
from food_recommender.infrastructure.clip_encoder import CLIPEncoder
from food_recommender.infrastructure.image_index import ImageIndexer
from food_recommender.infrastructure.image_search import PostgresImageSearch
from food_recommender.infrastructure.media import LocalMediaFiles
from food_recommender.infrastructure.persistence import create_database_engine
from food_recommender.retrieval.image_service import ImageRetrieval
from food_recommender.retrieval.models import ImageHit, TextPlan


async def execute(args: argparse.Namespace) -> None:
    encoder = await asyncio.to_thread(CLIPEncoder, args.clip_root)
    engine = create_database_engine(os.environ["DATABASE_URL"])
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        if args.command == "search":
            plan = TextPlan(
                args.query,
                categories=(Category.RECIPE,),
                sources=("recipe",),
                cuisine=args.cuisine,
            )
            hits = await ImageRetrieval(PostgresImageSearch(sessions), encoder).text(
                plan
            )
            print(TypeAdapter(tuple[ImageHit, ...]).dump_json(hits, indent=2).decode())
            return
        indexer = ImageIndexer(
            async_sessionmaker(engine, expire_on_commit=False),
            encoder,
            LocalMediaFiles(Path(os.environ["MEDIA_ROOT"])),
        )
        print(json.dumps(await indexer.build(), sort_keys=True))
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip-root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--cuisine")
    asyncio.run(execute(parser.parse_args()))


if __name__ == "__main__":
    main()
