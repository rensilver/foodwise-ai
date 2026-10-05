"""Shared atomic transaction boundary over feature-owned repository ports."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from food_recommender.application.auth.ports import AdminRepository
from food_recommender.application.catalog.ports import CatalogRepository
from food_recommender.application.conversations.ports import ConversationRepository
from food_recommender.application.media.cleanup_ports import MediaCleanupRepository
from food_recommender.application.media.ports import MediaRepository
from food_recommender.application.trends.ports import TrendRepository


class UnitOfWork(Protocol):
    media: MediaRepository
    admin: AdminRepository
    catalog: CatalogRepository
    conversations: ConversationRepository
    trends: TrendRepository
    cleanup: MediaCleanupRepository

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...
