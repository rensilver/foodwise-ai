"""Opaque trace journal and permanent tombstones; SQLite I/O is explicit and local."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any


class TraceLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, deleted INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS traces (id TEXT PRIMARY KEY, session TEXT NOT NULL REFERENCES sessions(id), confirmed INTEGER NOT NULL DEFAULT 0);
            """)
        path.chmod(0o600)

    def connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=0.1)

    def register(self, session: str, trace: str) -> bool:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO sessions(id) VALUES (?)", (session,))
            if db.execute(
                "SELECT deleted FROM sessions WHERE id=?", (session,)
            ).fetchone()[0]:
                return False
            db.execute(
                "INSERT OR IGNORE INTO traces(id,session) VALUES (?,?)",
                (trace, session),
            )
            return True

    def tombstone(self, session: str) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO sessions(id,deleted) VALUES (?,1) ON CONFLICT(id) DO UPDATE SET deleted=1",
                (session,),
            )

    def allowed(self, trace: str) -> bool:
        with self.connection() as db:
            row = db.execute(
                "SELECT s.deleted FROM traces t JOIN sessions s ON s.id=t.session WHERE t.id=?",
                (trace,),
            ).fetchone()
            return row is not None and not row[0]

    def pending(self) -> list[str]:
        with self.connection() as db:
            return [
                row[0]
                for row in db.execute(
                    "SELECT t.id FROM traces t JOIN sessions s ON s.id=t.session WHERE s.deleted=1 AND t.confirmed=0 ORDER BY t.id"
                )
            ]

    def confirm(self, trace: str) -> None:
        with self.connection() as db:
            db.execute("UPDATE traces SET confirmed=1 WHERE id=?", (trace,))

    def filter_and_export(
        self, spans: list[Any], export: Callable[[list[Any]], Any]
    ) -> Any:
        # Hold an interprocess SQLite writer lock through the bounded transport.
        # Deletion then follows an in-flight export, and all subsequent batches
        # see the tombstone. Lock contention drops telemetry, never business work.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            clean = []
            for span in spans:
                trace = f"{span.context.trace_id:032x}"
                row = db.execute(
                    "SELECT s.deleted FROM traces t JOIN sessions s ON s.id=t.session WHERE t.id=?",
                    (trace,),
                ).fetchone()
                if row is not None and not row[0]:
                    clean.append(span)
            return export(clean)
