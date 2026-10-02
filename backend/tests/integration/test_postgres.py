"""Real PostgreSQL/pgvector foundation contracts using an isolated test database."""

from pathlib import Path

import psycopg
import pytest
from pgvector import Vector
from pgvector.psycopg import register_vector

from food_recommender.infrastructure.health import local_readiness


def test_pgvector_and_limited_application_role(database: psycopg.Connection) -> None:
    with database.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication "
            "FROM pg_roles WHERE rolname = current_user"
        )
        assert cursor.fetchone() == (False, False, False, False)
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        assert cursor.fetchone() == ("0.8.6",)
        cursor.execute("SELECT current_setting('server_version_num')::int / 10000")
        assert cursor.fetchone() == (16,)


def test_vector_roundtrip_and_cosine_ranking(database: psycopg.Connection) -> None:
    register_vector(database)
    database.execute(
        "CREATE TABLE embedding_probe "
        "(id integer PRIMARY KEY, text vector(384), image vector(512))"
    )
    for identity, axis in ((1, 0), (2, 1)):
        text = [float(i == axis) for i in range(384)]
        image = [float(i == axis) for i in range(512)]
        database.execute(
            "INSERT INTO embedding_probe VALUES (%s, %s, %s)",
            (identity, Vector(text), Vector(image)),
        )
    rows = database.execute(
        "SELECT id, text <=> %s::vector AS distance "
        "FROM embedding_probe ORDER BY distance, id",
        (Vector([1.0] + [0.0] * 383),),
    ).fetchall()
    assert rows == [(1, 0.0), (2, 1.0)]
    row = database.execute(
        "SELECT text, image FROM embedding_probe WHERE id = 1"
    ).fetchone()
    assert row is not None
    assert row[0].dimensions() == 384 and row[1].dimensions() == 512
    assert row[0].to_list() == [1.0] + [0.0] * 383
    assert row[1].to_list() == [1.0] + [0.0] * 511
    assert database.execute(
        "SELECT id FROM embedding_probe ORDER BY image <=> %s::vector, id",
        (Vector([0.0, 1.0] + [0.0] * 510),),
    ).fetchall() == [(2,), (1,)]


def test_failed_vector_write_rolls_back_without_losing_prior_data(
    database: psycopg.Connection,
) -> None:
    database.execute("CREATE TABLE rollback_probe (id integer, value vector(384))")
    database.execute(
        "INSERT INTO rollback_probe VALUES (1, %s)", ([1.0] + [0.0] * 383,)
    )
    with pytest.raises(psycopg.errors.DataException):
        with database.transaction():
            database.execute(
                "INSERT INTO rollback_probe VALUES (2, %s)", ([1.0] + [0.0] * 383,)
            )
            database.execute("INSERT INTO rollback_probe VALUES (3, '[1,2,3]')")
    assert database.execute("SELECT id FROM rollback_probe").fetchall() == [(1,)]


@pytest.mark.asyncio
async def test_readiness_uses_real_postgres_and_media(
    database_url: str, tmp_path: Path
) -> None:
    assert await local_readiness(database_url, tmp_path) == {
        "database": True,
        "media": True,
    }
