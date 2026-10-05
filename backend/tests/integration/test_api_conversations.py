"""HTTP ownership contracts over real repositories, with no provider calls."""

import httpx
import pytest
import pytest_asyncio
from test_repositories import repositories  # noqa: F401, F811

from food_recommender.api.main import create_app
from food_recommender.application.conversations.service import ConversationService
from food_recommender.application.services import Services
from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork

TEST_TOKEN = "synthetic-test-token"


class Ready:
    async def check(self):
        return {"database": True, "media": True}


def settings(tmp_path):
    return Settings(
        OPENAI_API_KEY=TEST_TOKEN,
        DATABASE_URL="postgresql://fixture:fixture@localhost/foodwise_test",
        MCP_SERVER_URL="http://localhost:8001/mcp",
        MEDIA_ROOT=tmp_path,
        ADMIN_PASSWORD_HASH="$argon2id$v=19$m=19456,t=2,p=1$"
        + "YWFhYWFhYWFhYWFhYWFhYQ$"
        + "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
    )


@pytest_asyncio.fixture
async def api(repositories, tmp_path):  # noqa: F811
    factory, _ = repositories
    services = Services(
        Ready(), conversations=ConversationService(lambda: PostgresUnitOfWork(factory))
    )
    app = create_app(settings(tmp_path), services=services)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        yield client, app, services


@pytest.mark.asyncio
async def test_create_history_and_browser_isolation(api):
    client, app, _ = api
    created = await client.post("/api/v1/conversations")
    assert created.status_code == 201
    identity = created.json()["id"]
    cookie = created.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    history = await client.get(f"/api/v1/conversations/{identity}")
    assert history.status_code == 200
    assert history.json()["messages"] == []
    assert "session_id" not in history.text
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as stranger:
        assert (
            await stranger.get(f"/api/v1/conversations/{identity}")
        ).status_code == 404
        assert (
            await stranger.delete(f"/api/v1/conversations/{identity}")
        ).status_code == 404
    assert (await client.delete(f"/api/v1/conversations/{identity}")).status_code == 200
    assert (await client.get(f"/api/v1/conversations/{identity}")).status_code == 404


@pytest.mark.asyncio
async def test_invalid_ids_and_forged_cookie(api):
    client, _, _ = api
    client.cookies.set("foodwise_session", "not-a-token")
    assert (
        await client.get("/api/v1/conversations/11111111-1111-4111-8111-111111111111")
    ).status_code == 404
    await client.post("/api/v1/conversations")
    assert (await client.get("/api/v1/conversations/not-a-uuid")).status_code == 422
