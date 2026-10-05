"""Provider and tool failures retain typed, bounded and redacted outcomes."""

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from scripts.phase10_acceptance import (
    FixtureInference,
    FixtureTools,
    OwnedLeases,
    fixture_runner,
    load_labels,
)

from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.application.recommendations.reliability import (
    BudgetedInference,
    RunBudget,
    RunLimits,
    current_budget,
)
from food_recommender.application.recommendations.workflow import (
    ToolTransportError,
    TurnRequest,
)
from food_recommender.infrastructure.providers.openai import OpenAIStructuredInference
from food_recommender.retrieval.multimodal import MultimodalOutcome


@pytest.mark.asyncio
async def test_http_429_retry_after_then_success_without_model_switch():
    requests, waits = [], []

    def response(request):
        requests.append(json.loads(request.content))
        if len(requests) < 3:
            return httpx.Response(
                429, headers={"Retry-After": "2"}, text="private upstream details"
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    async def sleep(seconds):
        waits.append(seconds)

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        inference = BudgetedInference(
            OpenAIStructuredInference(
                http, SecretStr("synthetic-canary"), "configured-model"
            ),
            sleep=sleep,
            jitter=lambda: 0,
        )
        outcome = await UserProfileGenerator(inference).run(TurnRequest(message="rice"))
    assert outcome.status == "success"
    assert waits == [2, 2]
    assert len(requests) == 3
    assert {body["model"] for body in requests} == {"configured-model"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,payload,expected,calls",
    [
        (
            401,
            {"error": {"message": "private credential"}},
            "dependency_unavailable",
            1,
        ),
        (
            400,
            {"error": {"message": "model does not support json_schema"}},
            "invalid_response",
            3,
        ),
        (
            200,
            {"choices": [{"message": {"content": "{broken"}}]},
            "invalid_response",
            3,
        ),
        (
            200,
            {"choices": [{"message": {"refusal": "private refusal"}}]},
            "dependency_unavailable",
            1,
        ),
        (
            200,
            {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
            "dependency_unavailable",
            1,
        ),
    ],
)
async def test_nonretryable_credentials_capability_and_malformed_responses(
    status, payload, expected, calls
):
    requests = []

    def response(request):
        requests.append(json.loads(request.content))
        return httpx.Response(status, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        inference = BudgetedInference(
            OpenAIStructuredInference(
                http, SecretStr("synthetic-canary"), "fixed-model"
            )
        )
        token = current_budget.set(RunBudget(RunLimits()))
        try:
            outcome = await UserProfileGenerator(inference).run(
                TurnRequest(message="rice")
            )
        finally:
            current_budget.reset(token)
    assert outcome.code == expected
    assert len(requests) == calls
    assert {r["model"] for r in requests} == {"fixed-model"}
    assert "private" not in str(outcome)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["database", "mcp", "invalid-result"])
async def test_retrieval_downtime_is_failure_not_no_match(failure):
    class OfflineTools(FixtureTools):
        async def call(self, name, arguments):
            if failure == "database":
                return MultimodalOutcome(
                    "dependency_error", (), ("dependency unavailable",), 0
                )
            if failure == "mcp":
                raise ToolTransportError()
            return {"status": "success", "private": "upstream details"}

    owner, conversation = uuid4(), uuid4()
    tools = OfflineTools(load_labels()["cases"][0])
    provider = FixtureInference()
    runner = fixture_runner(provider, tools, OwnedLeases({conversation: owner}))
    result = await runner.run(
        owner, conversation, TurnRequest(message="rice", categories=["recipe"])
    )
    assert result["retrieval"]["code"] == "dependency_unavailable"
    assert result["final"]["status"] == "failure"
    assert not result["catalog"]
    assert not any("eligible_candidates" in call for call in provider.calls)
    assert "upstream details" not in json.dumps(result)
