"""Ports and dependencies for implemented application capabilities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from food_recommender.application.admin import AdminService
from food_recommender.application.admin_catalog import AdminCatalogService
from food_recommender.application.browse import BrowseService
from food_recommender.application.catalog import CatalogService
from food_recommender.application.conversations import ConversationService
from food_recommender.application.lookups import LookupService
from food_recommender.application.media import MediaService
from food_recommender.application.media_cleanup import MediaCleanupService
from food_recommender.application.messages import MessageService
from food_recommender.application.ports import UnitOfWork
from food_recommender.application.resources import CatalogResources
from food_recommender.application.trends import TrendService
from food_recommender.retrieval.multimodal import MultimodalRetrieval


class ReadinessProbe(Protocol):
    async def check(self) -> dict[str, bool]:
        """Report bounded local dependency checks, without provider calls."""
        ...


@dataclass(frozen=True)
class Services:
    readiness: ReadinessProbe
    transactions: Callable[[], UnitOfWork] | None = None
    close: Callable[[], Awaitable[None]] | None = None
    catalog: CatalogService | None = None
    browse: BrowseService | None = None
    conversations: ConversationService | None = None
    messages: MessageService | None = None
    media: MediaService | None = None
    admin: AdminService | None = None
    admin_catalog: AdminCatalogService | None = None
    media_cleanup: MediaCleanupService | None = None
    lookups: LookupService | None = None
    retrieval: MultimodalRetrieval | None = None
    resources: CatalogResources | None = None
    trends: TrendService | None = None
