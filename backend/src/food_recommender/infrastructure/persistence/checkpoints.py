"""Explicit, supported LangGraph schema setup, isolated from Alembic tables."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg import AsyncConnection
from psycopg.rows import dict_row


async def setup_checkpoints(database_url: str) -> None:
    # setup creates concurrent indexes and therefore needs an autocommit connection.
    async with await AsyncConnection.connect(
        database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        connect_timeout=5,
        options="-c statement_timeout=30000",
    ) as connection:
        cursor = await connection.execute(
            "SELECT to_regnamespace('foodwise_checkpoints') AS schema"
        )
        row = await cursor.fetchone()
        if row is None or row["schema"] is None:
            raise RuntimeError(
                "Administrator must create foodwise_checkpoints schema first"
            )
        await connection.execute("SET search_path TO foodwise_checkpoints")
        await AsyncPostgresSaver(connection).setup()


@asynccontextmanager
async def checkpoint_saver(database_url: str) -> AsyncIterator[AsyncPostgresSaver]:
    # Ordinary runtime opening never runs setup/migrations.
    async with await AsyncConnection.connect(
        database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        connect_timeout=5,
        options="-c statement_timeout=30000",
    ) as connection:
        await connection.execute("SET search_path TO foodwise_checkpoints")
        yield AsyncPostgresSaver(
            connection, serde=JsonPlusSerializer(allowed_msgpack_modules=None)
        )
