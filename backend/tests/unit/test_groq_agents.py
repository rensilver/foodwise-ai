import json

import httpx
import pytest
from pydantic import SecretStr

from food_recommender.infrastructure.providers.groq import GroqStructuredInference


@pytest.mark.asyncio
async def test_tool_selection_is_separate_and_rejects_undiscovered_tools():
    bodies = []

    def respond(request):
        body = json.loads(request.content)
        bodies.append(body)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "search_recipes",
                                        "arguments": '{"query":"rice"}',
                                    }
                                }
                            ]
                        }
                    }
                ],
                "usage": {"total_tokens": 12},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = GroqStructuredInference(
            client, SecretStr("synthetic-test"), "configured"
        )
        calls = await provider.select_tools(
            [{"role": "user", "content": "rice"}],
            {
                "search_recipes": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                }
            },
        )
        assert calls == (("search_recipes", {"query": "rice"}),)
        assert "response_format" not in bodies[0]
        assert bodies[0]["stream"] is False
        assert provider.usage[-1]["total_tokens"] == 12


@pytest.mark.asyncio
async def test_structured_generation_never_includes_tools():
    def respond(request):
        body = json.loads(request.content)
        assert "tools" not in body
        assert body["model"] == "configured"
        assert body["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"ok":true}'}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = GroqStructuredInference(
            client, SecretStr("synthetic-test"), "configured"
        )
        assert (
            await provider.generate(
                [{"role": "user", "content": "test"}], {"type": "object"}
            )
            == '{"ok":true}'
        )


@pytest.mark.asyncio
async def test_arbitrary_tool_name_and_nonobject_response_are_safe_failures():
    from food_recommender.application.inference import InferenceError

    for payload in (
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {"function": {"name": "delete_catalog", "arguments": "{}"}}
                        ]
                    }
                }
            ]
        },
        [],
    ):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=payload)
            )
        ) as client:
            provider = GroqStructuredInference(
                client, SecretStr("synthetic-test"), "configured"
            )
            with pytest.raises(InferenceError) as failure:
                await provider.select_tools([], {"search_recipes": {"type": "object"}})
            assert str(failure.value) == "Inference unavailable"


@pytest.mark.asyncio
async def test_rate_limit_retry_after_http_date_is_honored_without_response_text():
    from datetime import UTC, datetime

    from food_recommender.application.inference import InferenceError

    now = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                429,
                headers={"Retry-After": "Sun, 04 Oct 2026 12:00:04 GMT"},
                json={"secret": "private response"},
            )
        )
    ) as client:
        provider = GroqStructuredInference(
            client, SecretStr("synthetic-test"), "configured", clock=lambda: now
        )
        with pytest.raises(InferenceError) as failed:
            await provider.generate([], {})
        assert failed.value.retry_after == 4
        assert failed.value.retryable
        assert "private" not in str(failed.value)
