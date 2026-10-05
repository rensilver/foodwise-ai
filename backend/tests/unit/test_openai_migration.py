"""Provider migration contracts use synthetic credentials and mock HTTP only."""

import json

import httpx
import pytest
from pydantic import SecretStr

from food_recommender.application.recommendations.inference import InferenceError
from food_recommender.infrastructure.providers.openai import OpenAIStructuredInference


@pytest.mark.asyncio
async def test_openai_endpoint_auth_model_and_vision_payload():
    messages = [{"role": "user", "content": "Describe the image"}]
    media = "data:image/png;base64,c3ludGhldGlj"

    def respond(request):
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer synthetic-test"
        body = json.loads(request.content)
        assert body["model"] == "gpt-4o-mini"
        assert body["store"] is False
        assert body["stream"] is False
        assert body["messages"][-1]["content"][1]["image_url"]["url"] == media
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAIStructuredInference(
            client, SecretStr("synthetic-test"), "gpt-4o-mini"
        )
        assert (
            await provider.generate(messages, {"type": "object"}, image=media)
            == '{"ok":true}'
        )
    assert messages == [{"role": "user", "content": "Describe the image"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "choice",
    [
        {"finish_reason": "length", "message": {"content": '{"ok":true}'}},
        {"finish_reason": "content_filter", "message": {"content": '{"ok":true}'}},
        {
            "finish_reason": "stop",
            "message": {"content": '{"ok":true}', "refusal": "private refusal"},
        },
    ],
)
async def test_incomplete_or_refused_generation_is_a_redacted_failure(choice):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"choices": [choice]})
        )
    ) as client:
        provider = OpenAIStructuredInference(
            client, SecretStr("synthetic-test"), "gpt-4o-mini"
        )
        with pytest.raises(InferenceError, match="^Inference unavailable$") as failed:
            await provider.generate([], {})
        assert not failed.value.retryable


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,retryable", [(401, False), (403, False), (429, True), (500, True)]
)
async def test_provider_errors_remain_redacted_and_retryable_only_when_transient(
    status, retryable
):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                status, json={"error": {"message": "private-canary"}}
            )
        )
    ) as client:
        provider = OpenAIStructuredInference(
            client, SecretStr("synthetic-test"), "gpt-4o-mini"
        )
        with pytest.raises(InferenceError, match="^Inference unavailable$") as failed:
            await provider.generate([], {})
        assert failed.value.retryable is retryable
