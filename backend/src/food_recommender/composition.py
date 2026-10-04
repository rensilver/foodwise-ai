"""Process composition roots. Construction loads no models or service connections."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.agents.graph import WorkflowRoles
from food_recommender.agents.nodes.nutrition import NutritionExpert
from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.agents.nodes.rag import RAGRetriever
from food_recommender.agents.nodes.recommendation import RecommendationExpert
from food_recommender.agents.nodes.style import FoodStyleExpert
from food_recommender.agents.nodes.trend import FoodTrendAnalyst
from food_recommender.application.catalog import CatalogService
from food_recommender.application.conversations import ConversationService
from food_recommender.application.inference import Inference
from food_recommender.application.lookups import LookupService
from food_recommender.application.media_cleanup import MediaCleanupService
from food_recommender.application.ports import UnitOfWork
from food_recommender.application.reliability import (
    BudgetedInference,
    BudgetedTools,
    RunLimits,
)
from food_recommender.application.services import Services
from food_recommender.application.trends import TrendService
from food_recommender.application.workflow import ToolGateway
from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.embeddings.lazy import LazyCLIP, LazyMiniLM
from food_recommender.infrastructure.health import backend_readiness, local_readiness
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.query_media import AuthorizedQueryMedia
from food_recommender.infrastructure.persistence.repositories.lookups import (
    PostgresLookups,
)
from food_recommender.infrastructure.persistence.repositories.resources import (
    PostgresCatalogResources,
)
from food_recommender.infrastructure.persistence.search.image import PostgresImageSearch
from food_recommender.infrastructure.persistence.search.text import PostgresTextSearch
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.infrastructure.providers.tavily import TavilySearch
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
    http = httpx.AsyncClient(follow_redirects=False)

    def transactions() -> UnitOfWork:
        return PostgresUnitOfWork(sessions)

    async def close() -> None:
        await http.aclose()
        await engine.dispose()

    return Services(
        readiness=MCPReadiness(settings),
        close=close,
        trends=TrendService(
            TavilySearch(settings.tavily_api_key, http)
            if settings.tavily_api_key
            else None,
            transactions,
        ),
        lookups=LookupService(PostgresLookups(sessions)),
        resources=PostgresCatalogResources(sessions),
        retrieval=build_multimodal_retrieval(
            sessions,
            LazyMiniLM(settings.minilm_root) if settings.minilm_root else None,
            LazyCLIP(settings.clip_root) if settings.clip_root else None,
            settings.media_root,
        ),
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


def build_workflow_roles(
    inference: "Inference",
    rag_tools: "ToolGateway",
    trend_tools: "ToolGateway",
    *,
    limits: "RunLimits | None" = None,
    semaphore: "asyncio.Semaphore | None" = None,
    demo_profile_id: str | None = None,
    scoped_reviews: tuple[str, ...] = (),
) -> "WorkflowRoles":
    """Construct six roles over centrally managed, already scoped capabilities.

    Keep the Groq provider/semaphore and MCP client alive at the process root.
    Make MCP role views with application-issued session/run IDs for each turn;
    a model cannot choose identities, transport endpoints or review scope.
    """
    selected = limits if limits is not None else RunLimits()
    bounded = BudgetedInference(inference, limits=selected, semaphore=semaphore)
    return WorkflowRoles(
        UserProfileGenerator(bounded),
        RAGRetriever(bounded, BudgetedTools(rag_tools, limits=selected)),
        FoodTrendAnalyst(bounded, BudgetedTools(trend_tools, limits=selected)),
        FoodStyleExpert(bounded),
        NutritionExpert(bounded),
        RecommendationExpert(bounded),
        demo_profile_id=demo_profile_id,
        scoped_reviews=scoped_reviews,
    )
