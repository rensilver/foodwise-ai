"""Catalog use cases with atomic writes and post-commit media cleanup."""

from collections.abc import Callable

from food_recommender.application.media_cleanup import MediaCleanupService
from food_recommender.application.ports import UnitOfWork
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
