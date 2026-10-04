"""Explicit async PostgreSQL engine construction; no connections at import time."""

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def create_database_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("Persistence requires PostgreSQL with psycopg")
    return create_async_engine(
        url.set(drivername="postgresql+psycopg"),
        hide_parameters=True,
        pool_pre_ping=True,
    )
