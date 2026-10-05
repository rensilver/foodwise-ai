"""Process composition roots. Construction loads no models or service connections."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.agents.graph import WorkflowRoles, build_graph
from food_recommender.agents.nodes.nutrition import NutritionExpert
from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.agents.nodes.rag import RAGRetriever
from food_recommender.agents.nodes.recommendation import RecommendationExpert
from food_recommender.agents.nodes.style import FoodStyleExpert
from food_recommender.agents.nodes.trend import FoodTrendAnalyst
from food_recommender.agents.prompts import PROMPT_VERSION
from food_recommender.agents.runner import GraphRunner
from food_recommender.application.auth.service import AdminService
from food_recommender.application.catalog.admin import AdminCatalogService
from food_recommender.application.catalog.browse import BrowseService
from food_recommender.application.catalog.lookups import LookupService
from food_recommender.application.catalog.preparation import CatalogPreparation
from food_recommender.application.catalog.service import CatalogService
from food_recommender.application.conversations.messages import MessageService
from food_recommender.application.conversations.ports import ConversationRuns
from food_recommender.application.conversations.service import ConversationService
from food_recommender.application.media.cleanup import MediaCleanupService
from food_recommender.application.media.service import MediaService
from food_recommender.application.recommendations.activity import Progress, observer
from food_recommender.application.recommendations.inference import Inference
from food_recommender.application.recommendations.reliability import (
    BudgetedInference,
    BudgetedTools,
    RunLimits,
)
from food_recommender.application.recommendations.workflow import (
    ToolGateway,
    TurnRequest,
)
from food_recommender.application.services import Services
from food_recommender.application.trends.service import TrendService
from food_recommender.application.unit_of_work import UnitOfWork
from food_recommender.domain.values import Category
from food_recommender.infrastructure.auth import Argon2Verification
from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.embeddings.lazy import LazyCLIP, LazyMiniLM
from food_recommender.infrastructure.health import backend_readiness, local_readiness
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.media.uploads import ImageSanitizer
from food_recommender.infrastructure.persistence.checkpoints import checkpoint_saver
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.query_media import AuthorizedQueryMedia
from food_recommender.infrastructure.persistence.repositories.lookups import (
    PostgresLookups,
)
from food_recommender.infrastructure.persistence.repositories.resources import (
    PostgresCatalogResources,
)
from food_recommender.infrastructure.persistence.runs import PostgresConversationRuns
from food_recommender.infrastructure.persistence.search.image import PostgresImageSearch
from food_recommender.infrastructure.persistence.search.text import PostgresTextSearch
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.infrastructure.providers.openai import OpenAIStructuredInference
from food_recommender.infrastructure.providers.tavily import TavilySearch
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing
from food_recommender.ingestion.extraction import (
    ExtractionResult,
    ExtractionService,
    RecipeFields,
    RestaurantFields,
)
from food_recommender.mcp.client import AgentMCP, configured_client
from food_recommender.retrieval.embedding_contracts import (
    CLIP_REVISION,
    MINILM_REVISION,
)
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
    telemetry_settings: TelemetrySettings | None = None,
) -> Services:
    engine = create_database_engine(settings.database_url.get_secret_value())
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    def transactions() -> UnitOfWork:
        return PostgresUnitOfWork(sessions)

    cleanup = MediaCleanupService(transactions, LocalMediaFiles(settings.media_root))
    http = httpx.AsyncClient(follow_redirects=False)
    runs = PostgresConversationRuns(engine)
    inference = OpenAIStructuredInference(
        http, settings.openai_api_key, settings.openai_model
    )
    tracing = LazyTracing(
        telemetry_settings or TelemetrySettings(),
        revisions={
            "prompt_revision": PROMPT_VERSION,
            "embedding_revision": MINILM_REVISION + "-" + CLIP_REVISION,
            "dataset_revision": "catalog-ingestion-v1",
        },
        ledger_path=settings.media_root / ".telemetry" / "traces.sqlite",
    )
    workflow = PersistedWorkflow(settings, inference, runs, tracing=tracing)
    catalog = CatalogService(transactions, cleanup)
    browse = BrowseService(transactions)
    preview = AdminExtractionPreview(
        ExtractionService(inference, settings.media_root / "quarantine")
    )

    async def close() -> None:
        await tracing.close()
        await http.aclose()
        await engine.dispose()

    return Services(
        readiness=BackendReadiness(settings, probe),
        transactions=transactions,
        close=close,
        messages=MessageService(transactions, workflow, runs),
        media=MediaService(
            transactions, LocalMediaFiles(settings.media_root), ImageSanitizer()
        ),
        catalog=catalog,
        browse=browse,
        admin_catalog=AdminCatalogService(
            catalog,
            browse,
            CatalogPreparation(
                LazyMiniLM(settings.minilm_root) if settings.minilm_root else None
            ),
            preview,
        ),
        admin=AdminService(
            transactions,
            Argon2Verification(settings.admin_password_hash.get_secret_value()),
        ),
        conversations=ConversationService(
            transactions, cleanup, runs=runs, trace_cleanup=tracing
        ),
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

    Keep the OpenAI provider/semaphore and MCP client alive at the process root.
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


class PersistedWorkflow:
    def __init__(
        self,
        settings: Settings,
        inference: Inference,
        runs: ConversationRuns,
        *,
        tracing: LazyTracing | None = None,
    ) -> None:
        self.settings, self.runs = settings, runs
        self.tracing = tracing or LazyTracing(TelemetrySettings())
        self.inference = BudgetedInference(inference, semaphore=asyncio.Semaphore(3))
        self.client = configured_client(settings)

    async def execute(
        self,
        owner: UUID,
        conversation: UUID,
        run: UUID,
        request: TurnRequest,
        progress: Progress,
    ) -> dict[str, Any]:
        # Connection scopes are reused across all tools in a run. The centrally
        # configured reentrant client shares its connection across overlapping runs.
        async with (
            AgentMCP(self.client, "rag", session_id=owner, run_id=run) as rag,
            AgentMCP(self.client, "trend", run_id=run) as trends,
        ):
            database_url = self.settings.database_url.get_secret_value().replace(
                "postgresql+psycopg://", "postgresql://", 1
            )
            async with checkpoint_saver(database_url) as saver:
                roles = WorkflowRoles(
                    UserProfileGenerator(self.inference),
                    RAGRetriever(self.inference, BudgetedTools(rag)),
                    FoodTrendAnalyst(self.inference, BudgetedTools(trends)),
                    FoodStyleExpert(self.inference),
                    NutritionExpert(self.inference),
                    RecommendationExpert(self.inference),
                )
                if (
                    self.tracing.settings.enabled
                    and self.tracing.settings.conversation_export_verified
                ):
                    await asyncio.to_thread(self.tracing.initialize)
                runner = GraphRunner(
                    build_graph(roles, checkpointer=saver),
                    self.runs,
                    tracing=self.tracing,
                )
                token = observer.set(progress)
                try:
                    return await runner.run(
                        owner, conversation, request, run_id=run, leased=True
                    )
                finally:
                    observer.reset(token)


class AdminExtractionPreview:
    def __init__(self, service: ExtractionService) -> None:
        self.service = service

    async def preview(self, text: str, category: Category) -> ExtractionResult:
        return await self.service.preview(
            text,
            RestaurantFields if category == Category.RESTAURANT else RecipeFields,
            source="admin-preview",
            record_id="preview",
        )
