"""Conversation erasure and cleanup outcomes with session ownership."""

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.media_cleanup import MediaCleanupService
from food_recommender.application.ports import (
    ConversationSnapshot,
    MessageSnapshot,
    UnitOfWork,
)
from food_recommender.domain.preferences import Preferences


@dataclass(frozen=True)
class ConversationDeletion:
    conversation_id: UUID
    cleanup_pending: bool


class ConversationService:
    def __init__(
        self,
        transactions: Callable[[], UnitOfWork],
        cleanup: MediaCleanupService | None = None,
    ) -> None:
        self.transactions = transactions
        self.cleanup = cleanup

    async def session(
        self, token: str | None, *, create: bool = False
    ) -> tuple[UUID, str | None]:
        async with self.transactions() as transaction:
            if token and re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
                identity = await transaction.conversations.resolve_session(
                    hashlib.sha256(token.encode()).hexdigest()
                )
                if identity is not None:
                    return identity, None
            if not create:
                raise ApplicationError(ErrorCode.NOT_FOUND)
            token = secrets.token_urlsafe(32)
            identity = uuid4()
            await transaction.conversations.create_session(
                identity, hashlib.sha256(token.encode()).hexdigest()
            )
            await transaction.commit()
            return identity, token

    async def create(self, session_id: UUID) -> ConversationSnapshot:
        async with self.transactions() as transaction:
            result = await transaction.conversations.create(session_id, uuid4())
            await transaction.commit()
            return result

    async def history(
        self, session_id: UUID, conversation_id: UUID
    ) -> tuple[ConversationSnapshot, tuple[MessageSnapshot, ...], Preferences | None]:
        async with self.transactions() as transaction:
            conversation = await transaction.conversations.get(
                session_id, conversation_id
            )
            messages = await transaction.conversations.messages(
                session_id, conversation_id
            )
            profile = await transaction.conversations.get_profile(
                session_id, conversation_id
            )
            return conversation, messages, profile

    async def delete(
        self, session_id: UUID, conversation_id: UUID
    ) -> ConversationDeletion:
        async with self.transactions() as transaction:
            keys = await transaction.conversations.delete(session_id, conversation_id)
            await transaction.commit()
        pending = bool(keys)
        if self.cleanup is not None:
            try:
                await self.cleanup.run(keys=keys)
            except ApplicationError:
                # Context deletion is already committed; expose pending cleanup.
                return ConversationDeletion(conversation_id, bool(keys))
            async with self.transactions() as transaction:
                pending = await transaction.cleanup.has_pending(keys)
        return ConversationDeletion(conversation_id, pending)
