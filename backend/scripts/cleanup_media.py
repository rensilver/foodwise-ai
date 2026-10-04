"""Retry one bounded batch of committed, unreferenced private media jobs."""

import asyncio
import json
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.application.media_cleanup import MediaCleanupService
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


async def main() -> None:
    engine = create_database_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        result = await MediaCleanupService(
            lambda: PostgresUnitOfWork(sessions),
            LocalMediaFiles(Path(os.environ["MEDIA_ROOT"])),
        ).run()
        print(
            json.dumps(
                {
                    "removed": result.removed,
                    "retained": result.retained,
                    "failed": result.failed,
                }
            )
        )
        if result.failed:
            raise SystemExit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
