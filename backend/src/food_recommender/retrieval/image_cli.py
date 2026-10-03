"""Explicit offline image indexing; no inference on application startup."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.infrastructure.clip_encoder import CLIPEncoder
from food_recommender.infrastructure.image_index import ImageIndexer
from food_recommender.infrastructure.media import LocalMediaFiles
from food_recommender.infrastructure.persistence import create_database_engine


async def execute(args: argparse.Namespace) -> None:
    encoder = await asyncio.to_thread(CLIPEncoder, args.clip_root)
    engine = create_database_engine(os.environ["DATABASE_URL"])
    try:
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
    parser.add_argument("command", choices=("index",))
    asyncio.run(execute(parser.parse_args()))


if __name__ == "__main__":
    main()
