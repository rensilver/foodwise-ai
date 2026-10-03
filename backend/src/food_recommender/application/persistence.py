"""Catalog transaction boundaries; inference/embedding preparation happens first."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from food_recommender.application.errors import ApplicationError
from food_recommender.application.ports import MediaFiles, UnitOfWork
from food_recommender.domain.catalog import CatalogSnapshot, PreparedCatalog
from food_recommender.domain.values import EntityRef


class CatalogService:
    def __init__(
        self,
        transactions: Callable[[], UnitOfWork],
        cleanup: "MediaCleanupService | None" = None,
    ) -> None:
        self.transactions = transactions
        self.cleanup = cleanup

    async def create(self, prepared: PreparedCatalog) -> CatalogSnapshot:
        async with self.transactions() as transaction:
            result = await transaction.catalog.create(prepared)
            await transaction.commit()
            return result

    async def replace(
        self, ref: EntityRef, prepared: PreparedCatalog, *, expected_version: int
    ) -> CatalogSnapshot:
        async with self.transactions() as transaction:
            result = await transaction.catalog.replace(ref, prepared, expected_version)
            await transaction.commit()
        if self.cleanup is not None:
            await self.cleanup.run()
        return result

    async def delete(self, ref: EntityRef, *, expected_version: int) -> tuple[str, ...]:
        async with self.transactions() as transaction:
            keys = await transaction.catalog.delete(ref, expected_version)
            await transaction.commit()
        if self.cleanup is not None:
            await self.cleanup.run(keys=keys)
        return keys


@dataclass(frozen=True)
class CleanupResult:
    removed: int = 0
    retained: int = 0
    failed: int = 0


class MediaCleanupService:
    def __init__(
        self, transactions: Callable[[], UnitOfWork], files: MediaFiles
    ) -> None:
        self.transactions = transactions
        self.files = files

    async def run(self, *, keys: tuple[str, ...] | None = None) -> CleanupResult:
        # Bounded serial filesystem I/O outside the deletion transaction. Queue
        # rows are locked until acknowledged; failed jobs remain for a retry.
        removed = retained = failed = 0
        batches = (
            (None,)
            if keys is None
            else tuple(keys[start : start + 100] for start in range(0, len(keys), 100))
        )
        for batch in batches:
            async with self.transactions() as transaction:
                pending = await transaction.cleanup.pending(limit=100, keys=batch)
                for key in pending:
                    if await transaction.cleanup.referenced(key):
                        retained += 1
                    else:
                        try:
                            await self.files.delete(key)
                        except ApplicationError:
                            failed += 1
                            continue
                        removed += 1
                    await transaction.cleanup.complete(key)
                await transaction.commit()
        return CleanupResult(removed, retained, failed)


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
