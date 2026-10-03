"""Transaction-isolated catalog/provenance migrations on disposable PostgreSQL."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine


@pytest.fixture
def catalog(database_url: str) -> Iterator[tuple[Connection, Config]]:
    engine = create_engine(
        database_url.replace("postgresql://", "postgresql+psycopg://", 1),
        hide_parameters=True,
    )
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    with engine.connect() as connection:
        transaction = connection.begin()
        config.attributes["connection"] = connection
        try:
            command.upgrade(config, "head")
            connection.exec_driver_sql(
                "INSERT INTO demo_profiles (id) VALUES ('synthetic'), ('synthetic-profile')"
            )
            yield connection, config
        finally:
            transaction.rollback()
    engine.dispose()
