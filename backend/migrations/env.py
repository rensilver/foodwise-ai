"""Explicit PostgreSQL migrations without application/provider configuration."""

import os

from alembic import context
from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from food_recommender.infrastructure.provenance import Base


def migrate(connection: Connection) -> None:
    if connection.dialect.name != "postgresql":
        raise RuntimeError("Catalog migrations require PostgreSQL")
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied_connection = context.config.attributes.get("connection")
    if supplied_connection is not None:
        migrate(supplied_connection)
    else:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("Set DATABASE_URL explicitly to run migrations")
        url = make_url(dsn)
        if url.drivername not in {"postgresql", "postgresql+psycopg"}:
            raise RuntimeError("Catalog migrations require PostgreSQL with psycopg")
        engine = create_engine(
            url.set(drivername="postgresql+psycopg"),
            poolclass=NullPool,
            hide_parameters=True,
        )
        try:
            with engine.connect() as opened_connection:
                migrate(opened_connection)
        finally:
            engine.dispose()
