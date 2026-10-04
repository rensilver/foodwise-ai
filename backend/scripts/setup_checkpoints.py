"""Initialize supported LangGraph checkpoints explicitly, after Alembic upgrade."""

import asyncio
import os

from sqlalchemy.engine import make_url

from food_recommender.infrastructure.persistence.checkpoints import setup_checkpoints


def main() -> None:
    url = make_url(os.environ["DATABASE_URL"])
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise SystemExit("Checkpoint setup requires PostgreSQL with psycopg")
    asyncio.run(
        setup_checkpoints(
            url.set(drivername="postgresql").render_as_string(hide_password=False)
        )
    )
    print("Initialized supported LangGraph checkpoint tables.")


if __name__ == "__main__":
    main()
