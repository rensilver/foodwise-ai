"""Migration entry points require explicit configuration and support SQL previews."""

from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


def migration_config(output: StringIO | None = None) -> Config:
    return Config(str(Path(__file__).parents[2] / "alembic.ini"), output_buffer=output)


def test_migration_preview_needs_no_database_or_provider_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    output = StringIO()
    command.upgrade(migration_config(output), "head", sql=True)
    sql = output.getvalue()
    assert sql.startswith("BEGIN;")
    for table in (
        "restaurants",
        "recipes",
        "reviews",
        "sources",
        "source_records",
        "documents",
        "media",
    ):
        assert f"CREATE TABLE {table}" in sql
    assert "REFERENCES restaurants (id) ON DELETE RESTRICT ON UPDATE RESTRICT" in sql
    assert "COMMIT;" in sql


def test_provenance_only_upgrade_preview_preserves_existing_catalog() -> None:
    output = StringIO()
    command.upgrade(migration_config(output), "0001_catalog:0002_provenance", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE source_records" in sql
    assert "CREATE TABLE restaurants" not in sql
    assert "ALTER TABLE restaurants" not in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "raw_payload JSONB" in sql
    assert "REFERENCES media (id, source_record_id)" in sql


def test_provenance_only_downgrade_preview_preserves_catalog() -> None:
    output = StringIO()
    command.downgrade(
        migration_config(output), "0002_provenance:0001_catalog", sql=True
    )
    sql = output.getvalue()
    for table in ("documents", "media", "source_records", "sources"):
        assert f"DROP TABLE {table}" in sql
    assert "DROP TABLE recipes" not in sql


def test_online_migrations_require_explicit_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="Set DATABASE_URL explicitly"):
        command.upgrade(migration_config(), "head")


@pytest.mark.parametrize("url", ["sqlite://", "postgresql+asyncpg://localhost/unused"])
def test_online_migrations_reject_other_drivers_before_connecting(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(RuntimeError, match="require PostgreSQL with psycopg"):
        command.upgrade(migration_config(), "head")
