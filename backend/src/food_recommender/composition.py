"""Process composition roots. Construction loads no models or service connections."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.application.lookups import LookupService
from food_recommender.application.persistence import (
    CatalogService,
    ConversationService,
    MediaCleanupService,
)
from food_recommender.application.ports import UnitOfWork
from food_recommender.application.services import Services
from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.health import backend_readiness, local_readiness
from food_recommender.infrastructure.image_search import PostgresImageSearch
from food_recommender.infrastructure.lookups import PostgresLookups
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.media import LocalMediaFiles
from food_recommender.infrastructure.persistence import (
    PostgresUnitOfWork,
    create_database_engine,
)
from food_recommender.infrastructure.query_media import AuthorizedQueryMedia
from food_recommender.infrastructure.text_search import PostgresTextSearch
from food_recommender.retrieval.image_service import ImageRetrieval
from food_recommender.retrieval.multimodal import MultimodalRetrieval
from food_recommender.retrieval.ports import ImageEncoder, TextEncoder
from food_recommender.retrieval.service import TextRetrieval


@dataclass(frozen=True)
class BackendReadiness:
    settings: Settings
    probe: Callable[[Settings], Awaitable[dict[str, bool]]]

    async def check(self) -> dict[str, bool]:
        return await self.probe(self.settings)


@dataclass(frozen=True)
class MCPReadiness:
    settings: MCPSettings

    async def check(self) -> dict[str, bool]:
        return await local_readiness(
            self.settings.database_url.get_secret_value(),
            self.settings.media_root,
            writable=False,
        )


def build_backend_services(
    settings: Settings,
    *,
    probe: Callable[[Settings], Awaitable[dict[str, bool]]] = backend_readiness,
) -> Services:
    engine = create_database_engine(settings.database_url.get_secret_value())
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    def transactions() -> UnitOfWork:
        return PostgresUnitOfWork(sessions)

    cleanup = MediaCleanupService(transactions, LocalMediaFiles(settings.media_root))
    return Services(
        readiness=BackendReadiness(settings, probe),
        transactions=transactions,
        close=engine.dispose,
        catalog=CatalogService(transactions, cleanup),
        conversations=ConversationService(transactions, cleanup),
        media_cleanup=cleanup,
    )


def build_mcp_services(settings: MCPSettings) -> Services:
    engine = create_database_engine(settings.database_url.get_secret_value())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return Services(
        readiness=MCPReadiness(settings),
        close=engine.dispose,
        lookups=LookupService(PostgresLookups(sessions)),
    )


def build_multimodal_retrieval(
    sessions: async_sessionmaker[AsyncSession],
    text_encoder: TextEncoder | None,
    image_encoder: ImageEncoder | None,
    media_root: Path,
    *,
    allow_catalog_queries: bool = False,
) -> MultimodalRetrieval:
    """Wire explicitly provisioned models; construction loads no model/files."""
    return MultimodalRetrieval(
        TextRetrieval(PostgresTextSearch(sessions), text_encoder)
        if text_encoder
        else None,
        ImageRetrieval(
            PostgresImageSearch(sessions),
            image_encoder,
            AuthorizedQueryMedia(sessions, LocalMediaFiles(media_root)),
            allow_catalog_queries=allow_catalog_queries,
        )
        if image_encoder
        else None,
    )
