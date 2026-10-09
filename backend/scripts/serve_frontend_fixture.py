"""Opt-in Phase 9 browser fixture server on an isolated disposable database.

Uses real API/SQL/pgvector/checkpoints/HTTP MCP and offline pretrained encoders.
Only inference/trend boundaries are controlled. Never reads the owner's dotenv.
"""

import asyncio
import hashlib
import ipaddress
import json
import os
import socket
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from argon2 import PasswordHasher
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.applications import Starlette
from starlette.routing import Mount

from food_recommender.api.main import create_app
from food_recommender.application.auth.service import AdminService
from food_recommender.application.catalog.admin import AdminCatalogService
from food_recommender.application.catalog.browse import BrowseService
from food_recommender.application.catalog.preparation import CatalogPreparation
from food_recommender.application.catalog.service import CatalogService
from food_recommender.application.conversations.messages import MessageService
from food_recommender.application.conversations.service import ConversationService
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.media.cleanup import MediaCleanupService
from food_recommender.application.media.service import MediaService
from food_recommender.application.services import Services
from food_recommender.composition import (
    AdminExtractionPreview,
    PersistedWorkflow,
    build_multimodal_retrieval,
)
from food_recommender.domain.catalog import MediaData, RecipeData, RestaurantData
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.auth import Argon2Verification
from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.embeddings.lazy import LazyCLIP, LazyMiniLM
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.media.uploads import ImageSanitizer
from food_recommender.infrastructure.persistence.checkpoints import setup_checkpoints
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.indexing.image import ImageIndexer
from food_recommender.infrastructure.persistence.runs import PostgresConversationRuns
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing, sdk_factory
from food_recommender.ingestion.adapters import adapt_recipe, adapt_restaurant
from food_recommender.ingestion.extraction import ExtractionService, atomic_json
from food_recommender.mcp.server import create_server

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = Path(
    os.environ.get("FOODWISE_BROWSER_ARTIFACTS", ROOT / ".local-tmp/phase9/integration")
)


def loopback_network_only() -> None:
    resolve, connect = socket.getaddrinfo, socket.socket.connect

    def require(host):
        if host in {None, "localhost", b"localhost"}:
            return
        try:
            value = host.decode() if isinstance(host, bytes) else host
            if ipaddress.ip_address(value).is_loopback:
                return
        except ValueError:
            pass
        raise RuntimeError("Browser fixtures prohibit external network access")

    def guarded_resolve(host, *args, **kwargs):
        require(host)
        return resolve(host, *args, **kwargs)

    def guarded_connect(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            require(address[0])
        return connect(sock, address)

    socket.getaddrinfo = guarded_resolve
    socket.socket.connect = guarded_connect


class ControlledInference:
    model = "controlled-browser-fixture"

    def __init__(self):
        self.counts = {"profile_calls": 0, "cancelled_calls": 0}
        self.record()

    def record(self):
        atomic_json(ARTIFACTS / "provider-counts.json", self.counts)

    async def generate(self, messages, schema, *, image=None):
        context = json.loads(messages[1]["content"])
        if "source_text" in context:
            text = context["source_text"]
            return json.dumps(
                {
                    "name": text.split(".")[0],
                    "cuisine": "Italian" if "Italian" in text else None,
                }
            )
        if "request" in context:
            self.counts["profile_calls"] += 1
            self.record()
            text = context["request"]["message"]
            if text.startswith("Pause"):
                try:
                    await asyncio.sleep(20)
                except asyncio.CancelledError:
                    self.counts["cancelled_calls"] += 1
                    self.record()
                    raise
            return json.dumps(
                {"clarification": "Which city would you like?"}
                if text.startswith("Clarify")
                else {}
            )
        if "attempt" in context:
            return json.dumps({"query": context["message"], "use_images": True})
        if "deterministic_assessments" in context:
            return json.dumps({"assessments": context["deterministic_assessments"]})
        if "eligible_candidates" in context:
            indices, counts = [], {}
            for option in context["grounded_recommendations"]:
                category = option["entity"]["category"]
                counts[category] = counts.get(category, 0) + 1
                if counts[category] <= 5:
                    indices.append(option["recommendation_index"])
            return json.dumps({"recommendation_indices": indices})
        if "candidates" in context:
            return json.dumps(
                {
                    "selections": [
                        {
                            "candidate_index": item["candidate_index"],
                            "option_index": 0 if item["options"] else None,
                        }
                        for item in context["grounded_options"]
                    ]
                }
            )
        raise AssertionError("Unexpected fixture inference request")


class Ready:
    async def check(self):
        return {"database": True, "media": True, "mcp": True}


def fixture_tracing():
    """Explicit offline SDK outage injection for release browser acceptance."""
    from uuid import uuid4

    mode = os.environ.get("FOODWISE_TEST_TELEMETRY", "disabled")
    if mode == "disabled":
        return LazyTracing(TelemetrySettings(LANGFUSE_ENABLED=False))
    if mode != "unavailable":
        raise ValueError("Unknown browser telemetry fixture mode")
    from opentelemetry.sdk.trace.export import SpanExportResult

    class UnavailableExporter:
        def __init__(self):
            self.calls = 0

        def export(self, spans):
            self.calls += 1
            atomic_json(
                ARTIFACTS / "telemetry-counts.json", {"failed_exports": self.calls}
            )
            return SpanExportResult.FAILURE

        def shutdown(self):
            pass

    exporter = UnavailableExporter()
    settings = TelemetrySettings(
        LANGFUSE_ENABLED=True,
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
        LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",
        LANGFUSE_PUBLIC_KEY=uuid4().hex,
        LANGFUSE_SECRET_KEY="synthetic-unavailable",
        LANGFUSE_CORRELATION_KEY="synthetic-browser-correlation",
    )
    return LazyTracing(settings, factory=lambda s: sdk_factory(s, exporter))


async def main():
    dsn = os.environ["TEST_DATABASE_URL"]
    details = conninfo_to_dict(dsn)
    if details.get("dbname") != "foodwise_test" or details.get("host") not in {
        "localhost",
        "127.0.0.1",
    }:
        raise SystemExit(
            "Browser fixtures require an isolated localhost foodwise_test database."
        )
    os.environ.update(
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false"
    )
    loopback_network_only()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    media_root = ARTIFACTS / "media"
    media_root.mkdir(exist_ok=True)
    engine = create_database_engine(dsn)
    async with engine.begin() as connection:
        config = Config(str(ROOT / "backend/alembic.ini"))

        def migrate(sync):
            config.attributes["connection"] = sync
            command.upgrade(config, "head")

        await connection.run_sync(migrate)
    await setup_checkpoints(dsn)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    def transactions():
        return PostgresUnitOfWork(sessions)

    files = LocalMediaFiles(media_root)
    minilm = LazyMiniLM(
        Path(os.environ.get("P09_MINILM_ROOT", ROOT / ".local-tmp/minilm"))
    )
    clip = LazyCLIP(Path(os.environ.get("P09_CLIP_ROOT", ROOT / ".local-tmp/clip")))
    preparation = CatalogPreparation(minilm)
    catalog, browse = CatalogService(transactions), BrowseService(transactions)
    recipe = adapt_recipe(
        json.loads((ROOT / "data/Recipes.json").read_text())[0], "data/Recipes.json"
    ).data
    restaurant = adapt_restaurant(
        json.loads((ROOT / "data/structured_restaurant_data.json").read_text())[0],
        "data/structured_restaurant_data.json",
    ).data
    assert isinstance(recipe, RecipeData) and isinstance(restaurant, RestaurantData)
    for category, item in (
        (Category.RECIPE, recipe),
        (Category.RESTAURANT, restaurant),
    ):
        try:
            await browse.detail(EntityRef(category, item.id))
            continue
        except ApplicationError as error:
            if error.code != ErrorCode.NOT_FOUND:
                raise
        bundle = await preparation.prepare(item)
        if category == Category.RECIPE:
            content = (ROOT / "data/synthetic_recipe_images/recipe1.png").read_bytes()
            sanitized = await ImageSanitizer().prepare(content, "image/png")
            image_path = media_root / "course-recipe1.png"
            if image_path.exists():
                if image_path.read_bytes() != sanitized.content:
                    raise RuntimeError("Fixture image differs from its original source")
            else:
                await files.write("course-recipe1.png", sanitized.content)
            bundle = replace(
                bundle,
                media=(
                    MediaData(
                        id="course-recipe1-image",
                        source_record_id=bundle.records[0].id,
                        storage_key="course-recipe1.png",
                        mime_type=sanitized.mime_type,
                        byte_size=len(sanitized.content),
                        width=sanitized.width,
                        height=sanitized.height,
                        content_hash=hashlib.sha256(sanitized.content).hexdigest(),
                        ingestion_version="phase9-fixture-v1",
                        attribution="imported",
                    ),
                ),
            )
        await catalog.create(bundle)
    await ImageIndexer(sessions, clip, files).build()
    provider = ControlledInference()
    runs = PostgresConversationRuns(engine)
    password_hash = PasswordHasher().hash("phase9-fixture-password")
    configuration = Settings(
        OPENAI_API_KEY="synthetic-fixture-only",
        DATABASE_URL=dsn,
        MCP_SERVER_URL="http://127.0.0.1:8119/mcp/",
        MEDIA_ROOT=media_root,
        ADMIN_PASSWORD_HASH=password_hash,
        ALLOWED_ORIGINS=("http://127.0.0.1:3100",),
    )
    tracing = fixture_tracing()
    workflow = PersistedWorkflow(configuration, provider, runs, tracing=tracing)
    cleanup = MediaCleanupService(transactions, files)
    services = Services(
        Ready(),
        conversations=ConversationService(transactions, cleanup, runs=runs),
        messages=MessageService(transactions, workflow, runs),
        browse=browse,
        media=MediaService(transactions, files, ImageSanitizer()),
        admin=AdminService(transactions, Argon2Verification(password_hash)),
        admin_catalog=AdminCatalogService(
            catalog,
            browse,
            preparation,
            AdminExtractionPreview(
                ExtractionService(provider, media_root / "quarantine")
            ),
        ),
    )
    api_app = create_app(configuration, services=services)
    mcp = create_server(
        MCPSettings(DATABASE_URL=dsn, MEDIA_ROOT=media_root),
        services=Services(
            Ready(),
            retrieval=build_multimodal_retrieval(sessions, minilm, clip, media_root),
        ),
    )
    mcp_app = mcp.http_app(path="/")

    @asynccontextmanager
    async def lifespan(app):
        async with mcp_app.lifespan(app), api_app.router.lifespan_context(api_app):
            try:
                yield
            finally:
                await tracing.close()
                await engine.dispose()

    combined = Starlette(
        routes=[Mount("/mcp", mcp_app), Mount("/", api_app)], lifespan=lifespan
    )
    await uvicorn.Server(
        uvicorn.Config(combined, host="127.0.0.1", port=8119, log_level="warning")
    ).serve()


if __name__ == "__main__":
    asyncio.run(main())
