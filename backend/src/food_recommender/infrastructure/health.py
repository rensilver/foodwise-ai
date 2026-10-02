"""Bounded local dependency probes for Phase 1 service scaffolds."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import psycopg
from sqlalchemy.engine import make_url

if TYPE_CHECKING:
    from food_recommender.infrastructure.config import Settings


def media_available(root: Path, *, writable: bool) -> bool:
    try:
        if not root.is_dir():
            return False
        if writable:
            with tempfile.TemporaryFile(dir=root) as probe:
                probe.write(b"health")
                probe.flush()
        else:
            next(root.iterdir(), None)
        return True
    except OSError:
        return False


async def local_readiness(
    database_url: str, media_root: Path, *, writable: bool = True
) -> dict[str, bool]:
    async def database_available() -> bool:
        try:
            async with asyncio.timeout(5):
                # psycopg accepts a PostgreSQL URL, without SQLAlchemy's driver suffix.
                dsn = (
                    make_url(database_url)
                    .set(drivername="postgresql")
                    .render_as_string(hide_password=False)
                )
                async with await psycopg.AsyncConnection.connect(
                    dsn, connect_timeout=3
                ) as connection:
                    async with connection.cursor() as cursor:
                        await cursor.execute(
                            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                        )
                        row = await cursor.fetchone()
                        return row is not None and row[0] is True
        except Exception:
            # Never return driver exceptions: they may include credentials/hosts.
            return False

    database, media = await asyncio.gather(
        database_available(),
        asyncio.to_thread(media_available, media_root, writable=writable),
    )
    return {"database": database, "media": media}


async def backend_readiness(settings: Settings) -> dict[str, bool]:
    async def mcp_available() -> bool:
        try:
            health_url = httpx.URL(str(settings.mcp_server_url)).copy_with(
                path="/health/ready"
            )
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                response = await client.get(health_url)
                payload = response.json()
                return (
                    response.status_code == 200
                    and isinstance(payload, dict)
                    and payload.get("status") == "ready"
                )
        except (httpx.HTTPError, ValueError):
            return False

    local, mcp = await asyncio.gather(
        local_readiness(settings.database_url.get_secret_value(), settings.media_root),
        mcp_available(),
    )
    return local | {"mcp": mcp}


def health_payload(dependencies: dict[str, bool]) -> tuple[dict[str, object], int]:
    ready = all(dependencies.values())
    return {
        "status": "ready" if ready else "unavailable",
        "dependencies": {
            name: "ready" if value else "unavailable"
            for name, value in dependencies.items()
        },
    }, 200 if ready else 503
