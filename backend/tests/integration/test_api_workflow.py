"""HTTP -> six real roles -> MCP/pgvector -> PostgreSQL checkpoint acceptance."""

# ruff: noqa: F811

import asyncio
import hashlib
import json
import secrets
from uuid import uuid4

import httpx
import pytest
from fastmcp import Client
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker
from test_agent_checkpoints import workflow_store  # noqa: F401
from test_api_conversations import Ready, settings
from test_api_messages import events
from test_text_index import Encoder
from tests.unit.test_agent_acceptance import CulinaryReply

from food_recommender.api.main import create_app
from food_recommender.application.browse import BrowseService
from food_recommender.application.catalog import CatalogService
from food_recommender.application.catalog_preparation import CatalogPreparation
from food_recommender.application.conversations import ConversationService
from food_recommender.application.messages import MessageService
from food_recommender.application.services import Services
from food_recommender.composition import PersistedWorkflow, build_multimodal_retrieval
from food_recommender.domain.catalog import RecipeData
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.persistence.checkpoints import checkpoint_saver
from food_recommender.infrastructure.persistence.models.context import BrowserSession
from food_recommender.infrastructure.persistence.runs import PostgresConversationRuns
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.mcp.server import create_server


async def application(database_url, workflow_store, tmp_path, provider):
    engine, owner, stranger, conversation = workflow_store
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    def transactions():
        return PostgresUnitOfWork(sessions)

    token = secrets.token_urlsafe(32)
    async with engine.begin() as connection:
        await connection.execute(
            update(BrowserSession)
            .where(BrowserSession.id == owner)
            .values(token_hash=hashlib.sha256(token.encode()).hexdigest())
        )
    preparation = CatalogPreparation(Encoder())
    await CatalogService(transactions).create(
        await preparation.prepare(
            RecipeData(
                id="http-recipe",
                source_id="fixture",
                source_record_id="http-recipe",
                name="Italian tomato rice",
                normalized_cuisine="italian",
                ingredients=("rice", "tomato", "basil"),
                directions=("simmer rice",),
            )
        )
    )
    server = create_server(
        MCPSettings(DATABASE_URL=database_url, MEDIA_ROOT=tmp_path),
        services=Services(
            Ready(),
            retrieval=build_multimodal_retrieval(sessions, Encoder(), None, tmp_path),
        ),
    )
    configuration = settings(tmp_path).model_copy(
        update={"database_url": settings(tmp_path).database_url.__class__(database_url)}
    )
    runs = PostgresConversationRuns(engine)
    workflow = PersistedWorkflow(configuration, provider, runs)
    workflow.client = Client(server)
    services = Services(
        Ready(),
        conversations=ConversationService(transactions),
        messages=MessageService(transactions, workflow, runs),
        browse=BrowseService(transactions),
    )
    app = create_app(configuration, services=services)
    return app, token, owner, conversation, workflow


@pytest.mark.asyncio
async def test_http_real_graph_retrieval_checkpoint_followup_and_replay(
    database_url, workflow_store, tmp_path
):  # noqa: F811
    provider = CulinaryReply()
    app, token, owner, conversation, workflow = await application(
        database_url, workflow_store, tmp_path, provider
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost",
        cookies={"foodwise_session": token},
    ) as client:
        path = f"/api/v1/conversations/{conversation}/messages"
        request = {
            "message": "Italian tomato rice",
            "categories": ["recipe"],
            "client_request_id": str(uuid4()),
        }
        first = await client.post(path, json=request)
        assert first.status_code == 200
        data = events(first)
        assert data[-1]["outcome"] == "completed"
        recommendation = next(e for e in data if e["event"] == "recommendations")
        assert (
            recommendation["result"]["recommendations"][0]["entity"]["id"]
            == "http-recipe"
        )
        assert recommendation["evidence"][0]["citations"][0]["document_id"]
        assert {e["agent"] for e in data if e["event"] == "progress"} == {
            "user_profile_generator",
            "rag_retriever",
            "food_trend_analyst",
            "food_style_expert",
            "nutrition_expert",
            "recommendation_expert",
        }
        assert (await client.post(path, json=request)).status_code == 409
        second = await client.post(
            path,
            json={
                "message": "now more Italian",
                "client_request_id": str(uuid4()),
                "explicit": {
                    "constraints": [
                        {
                            "kind": "allergen",
                            "value": "peanut",
                            "strength": "hard",
                            "origin": "explicit",
                        }
                    ]
                },
            },
        )
        assert events(second)[-1]["outcome"] == "completed"
        third = await client.post(
            path, json={"message": "another option", "client_request_id": str(uuid4())}
        )
        assert events(third)[-1]["outcome"] == "completed"
        history = (await client.get(f"/api/v1/conversations/{conversation}")).json()
        assert len(history["messages"]) == 6
        assert history["preferences"]["constraints"][0]["value"] == "peanut"
        async with checkpoint_saver(database_url) as saver:
            checkpoint = await saver.aget_tuple(
                {"configurable": {"thread_id": str(conversation)}}
            )
            assert checkpoint.checkpoint["channel_values"]["lifecycle"] == "completed"


@pytest.mark.asyncio
async def test_disconnect_cancels_real_checkpoint_and_releases_database_lease(
    database_url, workflow_store, tmp_path
):  # noqa: F811
    entered, cancelled = asyncio.Event(), asyncio.Event()

    class Slow(CulinaryReply):
        async def generate(self, *args, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    app, token, owner, conversation, workflow = await application(
        database_url, workflow_store, tmp_path, Slow()
    )
    body = json.dumps({"message": "rice", "client_request_id": str(uuid4())}).encode()
    sent_body = False

    async def receive():
        nonlocal sent_body
        if not sent_body:
            sent_body = True
            return {"type": "http.request", "body": body, "more_body": False}
        await entered.wait()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://localhost",
            cookies={"foodwise_session": token},
        ) as concurrent:
            blocked = await concurrent.post(
                f"/api/v1/conversations/{conversation}/messages",
                json={"message": "another", "client_request_id": str(uuid4())},
            )
            assert blocked.status_code == 409
            assert "text/event-stream" not in blocked.headers["content-type"]
        return {"type": "http.disconnect"}

    sent = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": f"/api/v1/conversations/{conversation}/messages",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"localhost"),
            (b"content-type", b"application/json"),
            (b"cookie", ("foodwise_session=" + token).encode()),
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("localhost", 80),
    }
    await asyncio.wait_for(app(scope, receive, send), 10)
    assert cancelled.is_set()
    engine, *_ = workflow_store
    async with PostgresConversationRuns(engine).lease(conversation, owner):
        pass
    async with checkpoint_saver(database_url) as saver:
        checkpoint = await saver.aget_tuple(
            {"configurable": {"thread_id": str(conversation)}}
        )
        assert checkpoint.checkpoint["channel_values"]["lifecycle"] == "cancelled"
    # Reading history does not invoke the cancelled provider or resume its graph.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost",
        cookies={"foodwise_session": token},
    ) as client:
        history = await client.get(f"/api/v1/conversations/{conversation}")
        assert history.status_code == 200 and len(history.json()["messages"]) == 1
