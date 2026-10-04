"""Conversation erasure and cleanup outcomes with session ownership."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from food_recommender.application.errors import ApplicationError
from food_recommender.application.media_cleanup import MediaCleanupService
from food_recommender.application.ports import UnitOfWork


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
