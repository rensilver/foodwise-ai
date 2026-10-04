"""Validated POST streams and stored completion over the real database."""

import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from test_api_conversations import api  # noqa: F401
from test_repositories import repositories  # noqa: F401

from food_recommender.application.messages import MessageService
from food_recommender.domain.values import AgentRole


class Workflow:
    def __init__(self):
        self.calls = 0

    async def execute(self, owner, conversation, run, request, progress):
        self.calls += 1
        await progress(AgentRole.USER_PROFILE_GENERATOR, "completed")
        if request.message == "fail":
            raise RuntimeError("private exception content")
        return {"profile": {"clarification": "Which city?"}, "final": None}


def events(response):
    return [
        json.loads(part.split("data: ")[1])
        for part in response.text.split("\n\n")
        if "data: " in part
    ]


@pytest.mark.asyncio
async def test_message_stream_and_history_commit(api):  # noqa: F811
    client, app, services = api
    workflow = Workflow()
    app.state.services = replace(
        services, messages=MessageService(services.conversations.transactions, workflow)
    )
    identity = (await client.post("/api/v1/conversations")).json()["id"]
    request = {"message": "rice", "client_request_id": str(uuid4())}
    response = await client.post(
        f"/api/v1/conversations/{identity}/messages", json=request
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    data = events(response)
    assert [e["event"] for e in data] == ["progress", "clarification", "done"]
    assert len({e["run_id"] for e in data}) == 1
    UUID(data[-1]["run_id"])
    assert data[-1]["outcome"] == "clarification"
    history = (await client.get(f"/api/v1/conversations/{identity}")).json()
    assert len(history["messages"]) == 2
    assert (
        next(
            message for message in history["messages"] if message["role"] == "assistant"
        )["payload"]["event"]
        == "clarification"
    )
    replay = await client.post(
        f"/api/v1/conversations/{identity}/messages", json=request
    )
    assert replay.status_code == 409
    assert workflow.calls == 1


@pytest.mark.asyncio
async def test_pre_stream_validation_and_post_stream_safe_failure(api):  # noqa: F811
    client, app, services = api
    workflow = Workflow()
    app.state.services = replace(
        services, messages=MessageService(services.conversations.transactions, workflow)
    )
    identity = (await client.post("/api/v1/conversations")).json()["id"]
    path = f"/api/v1/conversations/{identity}/messages"
    invalid = await client.post(
        path, json={"message": " ", "client_request_id": str(uuid4())}
    )
    assert (
        invalid.status_code == 422
        and "text/event-stream" not in invalid.headers["content-type"]
    )
    missing_media = await client.post(
        path,
        json={
            "message": "rice",
            "media_id": "missing",
            "client_request_id": str(uuid4()),
        },
    )
    assert missing_media.status_code == 404
    failure = await client.post(
        path, json={"message": "fail", "client_request_id": str(uuid4())}
    )
    assert [e["event"] for e in events(failure)] == ["progress", "error", "done"]
    assert "private exception" not in failure.text
    assert events(failure)[-1]["outcome"] == "failed"
