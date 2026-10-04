"""Cross-process transaction advisory leases; ownership is verified in PostgreSQL."""

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.infrastructure.persistence.models.context import Conversation


class PostgresConversationRuns:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    @asynccontextmanager
    async def lease(
        self, conversation_id: UUID, session_id: UUID
    ) -> AsyncIterator[None]:
        key = int.from_bytes(
            hashlib.blake2b(
                b"foodwise-run:" + conversation_id.bytes, digest_size=8
            ).digest(),
            signed=True,
        )
        async with self.engine.connect() as connection:
            async with connection.begin():
                owned = await connection.scalar(
                    select(Conversation.id).where(
                        Conversation.id == conversation_id,
                        Conversation.session_id == session_id,
                    )
                )
                if owned is None:
                    raise ApplicationError(ErrorCode.NOT_FOUND)
                acquired = await connection.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}
                )
                if not acquired:
                    raise ApplicationError(ErrorCode.CONFLICT)
                # Prevent context deletion while the owned run holds its lease.
                owned = await connection.scalar(
                    select(Conversation.id)
                    .where(
                        Conversation.id == conversation_id,
                        Conversation.session_id == session_id,
                    )
                    .with_for_update(read=True)
                )
                if owned is None:
                    raise ApplicationError(ErrorCode.NOT_FOUND)
                yield None
