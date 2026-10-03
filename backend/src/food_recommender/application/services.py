"""Ports and dependencies for implemented application capabilities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from food_recommender.application.lookups import LookupService
from food_recommender.application.persistence import (
    CatalogService,
    ConversationService,
    MediaCleanupService,
)
from food_recommender.application.ports import UnitOfWork
from food_recommender.application.trends import TrendService
from food_recommender.mcp.resources import CatalogResources
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
    conversations: ConversationService | None = None
    media_cleanup: MediaCleanupService | None = None
    lookups: LookupService | None = None
    retrieval: MultimodalRetrieval | None = None
    resources: CatalogResources | None = None
    trends: TrendService | None = None
