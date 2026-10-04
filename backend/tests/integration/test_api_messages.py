"""Validated POST streams and stored completion over the real database."""

# ruff: noqa: F811

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
        return {
            "profile": {
                "categories": ["recipe"],
                "preferences": {},
                "clarification": "Which city?",
            },
            "final": None,
        }


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


@pytest.mark.asyncio
async def test_completed_recommendations_include_citations_and_are_committed_before_delivery(
    api,
):  # noqa: F811
    from pydantic_core import to_jsonable_python
    from tests.unit.agent_fixtures import candidate

    from food_recommender.application.contracts import event_adapter
    from food_recommender.domain.events import RecommendationsEvent
    from food_recommender.domain.experts import (
        AgentSuccess,
        AgentUnavailable,
        ProfileResult,
        RetrievalResult,
    )
    from food_recommender.domain.preferences import Preferences
    from food_recommender.domain.recommendations import (
        Recommendation,
        RecommendationResult,
    )
    from food_recommender.domain.values import Category

    client, app, services = api
    food = candidate()

    class Completed:
        async def execute(self, owner, conversation, run, request, progress):
            return to_jsonable_python(
                {
                    "profile": ProfileResult((Category.RECIPE,), Preferences()),
                    "retrieval": AgentSuccess(RetrievalResult((food.evidence,), 1)),
                    "catalog": (food,),
                    "trend": AgentUnavailable("trends_unavailable"),
                    "style": AgentUnavailable("style_unavailable"),
                    "nutrition": AgentUnavailable("nutrition_unavailable"),
                    "final": AgentSuccess(
                        RecommendationResult(
                            (
                                Recommendation(
                                    food.evidence.entity,
                                    food.evidence.citations[0].excerpt,
                                    (food.evidence.citations[0].id,),
                                ),
                            )
                        )
                    ),
                }
            )

    service = MessageService(services.conversations.transactions, Completed())
    app.state.services = replace(services, messages=service)
    identity = (await client.post("/api/v1/conversations")).json()["id"]
    owner, _ = await services.conversations.session(
        client.cookies.get("foodwise_session")
    )
    from food_recommender.application.messages import MessageSubmission

    turn = await service.prepare(
        owner,
        UUID(identity),
        MessageSubmission(message="rice", client_request_id=uuid4()),
    )
    async for event in service.events(turn):
        if isinstance(event, RecommendationsEvent):
            _, messages, _ = await services.conversations.history(owner, UUID(identity))
            assert len(messages) == 2
            assert event.evidence[0].citations[0].document_id
            assert event_adapter.validate_json(event_adapter.dump_json(event)) == event


@pytest.mark.asyncio
async def test_unexpected_failure_is_stored_and_stale_clarification_cannot_mask_failure(
    api,
):  # noqa: F811
    client, app, services = api

    class Broken:
        async def execute(self, *args):
            return {
                "profile": {"clarification": "Old question"},
                "profile_outcome": {
                    "status": "failure",
                    "code": "invalid_response",
                    "retryable": False,
                },
                "final": {
                    "status": "failure",
                    "code": "invalid_response",
                    "retryable": False,
                },
            }

    app.state.services = replace(
        services, messages=MessageService(services.conversations.transactions, Broken())
    )
    identity = (await client.post("/api/v1/conversations")).json()["id"]
    response = await client.post(
        f"/api/v1/conversations/{identity}/messages",
        json={"message": "rice", "client_request_id": str(uuid4())},
    )
    assert [e["event"] for e in events(response)] == ["error", "done"]
    history = (await client.get(f"/api/v1/conversations/{identity}")).json()
    assert any(
        message["payload"].get("event") == "error" for message in history["messages"]
    )


@pytest.mark.asyncio
async def test_stream_deadline_emits_stored_budget_failure(api):  # noqa: F811
    import asyncio

    from food_recommender.application.reliability import RunLimits

    client, app, services = api

    class Stalled:
        async def execute(self, *args):
            await asyncio.Event().wait()

    app.state.services = replace(
        services,
        messages=MessageService(
            services.conversations.transactions,
            Stalled(),
            limits=RunLimits(call_seconds=0.01, run_seconds=0.01),
        ),
    )
    identity = (await client.post("/api/v1/conversations")).json()["id"]
    response = await client.post(
        f"/api/v1/conversations/{identity}/messages",
        json={"message": "rice", "client_request_id": str(uuid4())},
    )
    data = events(response)
    assert [e["event"] for e in data] == ["error", "done"]
    assert data[0]["code"] == "budget_exhausted"
    history = (await client.get(f"/api/v1/conversations/{identity}")).json()
    assert any(
        message["payload"].get("code") == "budget_exhausted"
        for message in history["messages"]
    )
