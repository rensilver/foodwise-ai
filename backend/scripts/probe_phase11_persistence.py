"""Container-side P11-02 probes; run only in the verifier's disposable database."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import TypedDict
from uuid import UUID, uuid4

import psycopg
from langgraph.graph import END, START, StateGraph
from PIL import Image
from psycopg import sql
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.values import ConstraintKind, Origin, Strength
from food_recommender.infrastructure.config import load_settings
from food_recommender.infrastructure.health import backend_readiness
from food_recommender.infrastructure.persistence.checkpoints import checkpoint_saver
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


def dsn() -> str:
    return os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )


def snapshot() -> dict:
    """Hash complete rows, including vectors/timestamps, without exporting content."""
    tables = {}
    with psycopg.connect(dsn()) as connection:
        names = connection.execute(
            "SELECT schemaname, tablename FROM pg_tables WHERE schemaname IN "
            "('public', 'foodwise_checkpoints') ORDER BY schemaname, tablename"
        ).fetchall()
        for schema, table in names:
            rows = connection.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} AS t").format(
                    sql.Identifier(schema, table)
                )
            ).fetchall()
            payload = json.dumps(sorted(row[0] for row in rows)).encode()
            tables[f"{schema}.{table}"] = {
                "rows": len(rows),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        files = []
        for key, expected_hash, size in connection.execute(
            "SELECT storage_key, content_hash, byte_size FROM media ORDER BY storage_key"
        ):
            content = (Path(os.environ["MEDIA_ROOT"]) / key).read_bytes()
            actual_hash = hashlib.sha256(content).hexdigest()
            assert actual_hash == expected_hash and len(content) == size
            with Image.open(Path(os.environ["MEDIA_ROOT"]) / key) as image:
                image.verify()
            files.append((key, actual_hash, size))
        role = connection.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication "
            "FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        assert role == (False, False, False, False)
        return {
            "tables": tables,
            "media": {
                "files": len(files),
                "sha256": hashlib.sha256(json.dumps(files).encode()).hexdigest(),
                "all_hashes_sizes_and_decoding_valid": True,
            },
            "migration": connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()[0],
            "postgres": connection.execute("SHOW server_version").fetchone()[0],
            "pgvector": connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()[0],
            "application_role_limited": True,
        }


class ProbeState(TypedDict):
    turns: int
    restriction: str


def advance(state: ProbeState) -> dict:
    return {"turns": state["turns"] + 1}


async def context(conversation_id: UUID, *, seed: bool) -> dict:
    """Persist real application context and a synthetic control-graph checkpoint."""
    engine = create_database_engine(os.environ["DATABASE_URL"])
    preferences = Preferences(
        constraints=(
            Constraint(
                ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT
            ),
        )
    )
    try:
        with psycopg.connect(dsn()) as connection:
            owner = connection.execute(
                "SELECT session_id FROM conversations WHERE id = %s",
                (conversation_id,),
            ).fetchone()[0]
        async with PostgresUnitOfWork(async_sessionmaker(engine)) as uow:
            if seed:
                await uow.conversations.append_message(
                    owner,
                    conversation_id,
                    uuid4(),
                    "user",
                    "Synthetic persistence probe",
                )
                await uow.conversations.save_profile(
                    owner, conversation_id, preferences
                )
                await uow.commit()
            assert (
                await uow.conversations.get_profile(owner, conversation_id)
                == preferences
            )
            assert len(await uow.conversations.messages(owner, conversation_id)) == 1
        async with checkpoint_saver(dsn()) as saver:
            builder = StateGraph(ProbeState)
            builder.add_node("persistence_control", advance)
            builder.add_edge(START, "persistence_control")
            builder.add_edge("persistence_control", END)
            graph = builder.compile(checkpointer=saver)
            config = {"configurable": {"thread_id": str(conversation_id)}}
            if seed:
                result = await graph.ainvoke(
                    {"turns": 0, "restriction": "peanut"}, config
                )
                assert result == {"turns": 1, "restriction": "peanut"}
            else:
                saved = await graph.aget_state(config)
                assert saved.values == {"turns": 1, "restriction": "peanut"}
                result = await graph.ainvoke({}, config)
                assert result == {"turns": 2, "restriction": "peanut"}
        return {
            "messages": 1,
            "profile_preserved": True,
            "checkpoint_turns": result["turns"],
        }
    finally:
        await engine.dispose()


async def readiness_variants() -> dict:
    settings = load_settings()
    results = {}
    for dependency, field in (
        ("media", "media_root"),
        ("catalog_encoder", "minilm_root"),
    ):
        changed = settings.model_copy(update={field: Path("/absent-p11-02")})
        result = await backend_readiness(changed)
        assert result[dependency] is False
        assert all(value for name, value in result.items() if name != dependency)
        results[dependency] = result
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=("snapshot", "seed-context", "advance-context", "readiness"),
    )
    parser.add_argument("--conversation", type=UUID)
    args = parser.parse_args()
    if args.operation == "snapshot":
        result = snapshot()
    elif args.operation == "readiness":
        result = asyncio.run(readiness_variants())
    else:
        if args.conversation is None:
            parser.error("--conversation is required for context probes")
        result = asyncio.run(
            context(args.conversation, seed=args.operation == "seed-context")
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
