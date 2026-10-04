"""Bounded cleanup of unreferenced files through storage and transaction ports."""

from collections.abc import Callable
from dataclasses import dataclass

from food_recommender.application.errors import ApplicationError
from food_recommender.application.ports import MediaFiles, UnitOfWork


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
