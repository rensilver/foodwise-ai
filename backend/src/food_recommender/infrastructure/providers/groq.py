"""Groq structured generation boundary; independent text/vision configuration."""

import asyncio
import json
from time import perf_counter
from typing import Any

import httpx
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import SecretStr

from food_recommender.application.inference import InferenceError


class GroqStructuredInference:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: SecretStr,
        model: str,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
        self.usage: list[dict[str, int | float | str]] = []
        self.client = client
        self.api_key = api_key
        self.model = model
        self.semaphore = semaphore if semaphore is not None else asyncio.Semaphore(3)

    async def generate(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        image: str | None = None,
    ) -> str:
        request_messages: list[dict[str, Any]] = list(messages)
        if image is not None:
            if not image.startswith(
                (
                    "data:image/png;base64,",
                    "data:image/jpeg;base64,",
                    "data:image/webp;base64,",
                )
            ):
                raise ValueError("Vision requires a validated image data URI")
            last = request_messages[-1]
            request_messages[-1] = {
                "role": last["role"],
                "content": [
                    {"type": "text", "text": last["content"]},
                    {"type": "image_url", "image_url": {"url": image}},
                ],
            }
        payload = await self._request(
            {
                "messages": request_messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "culinary_response",
                        "strict": False,
                        "schema": schema,
                    },
                },
            }
        )
        try:
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError
            return content
        except (KeyError, IndexError, TypeError, ValueError):
            raise InferenceError(schema_error=True) from None

    async def _request(self, body: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        async with self.semaphore:
            try:
                response = await self.client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key.get_secret_value()}"
                    },
                    json={
                        "model": self.model,
                        "stream": False,
                        "max_completion_tokens": 4096,
                        **body,
                    },
                    timeout=30,
                )
            except (httpx.TimeoutException, httpx.TransportError):
                raise InferenceError(retryable=True) from None
            if response.is_error:
                try:
                    retry_after = max(
                        0.0, min(float(response.headers.get("Retry-After", "0")), 120.0)
                    )
                except ValueError:
                    retry_after = 0.0
                raise InferenceError(
                    retryable=response.status_code == 429
                    or response.status_code >= 500,
                    retry_after=retry_after,
                    schema_error=response.status_code == 400,
                )
            try:
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError
            except (ValueError, TypeError):
                raise InferenceError(schema_error=True) from None
            usage = payload.get("usage", {})
            self.usage.append(
                {
                    "model": self.model,
                    "elapsed_ms": (perf_counter() - started) * 1000,
                    **{
                        key: value
                        for key, value in usage.items()
                        if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
                        and type(value) is int
                    },
                }
            )
            return payload

    async def select_tools(
        self, messages: list[dict[str, str]], schemas: dict[str, dict[str, Any]]
    ) -> tuple[tuple[str, dict[str, Any]], ...]:
        """Select only from caller-supplied discovered schemas; never executes tools."""
        if not schemas:
            return ()
        payload = await self._request(
            {
                "messages": messages,
                "tools": [
                    {
                        "type": "function",
                        "function": {"name": name, "parameters": schema},
                    }
                    for name, schema in schemas.items()
                ],
                "tool_choice": "auto",
            }
        )
        try:
            calls = payload["choices"][0]["message"].get("tool_calls", [])
            if not isinstance(calls, list) or len(calls) > 6:
                raise ValueError
            result = []
            for call in calls:
                function = call["function"]
                name = function["name"]
                if name not in schemas:
                    raise ValueError
                arguments = json.loads(function["arguments"])
                Draft202012Validator(schemas[name]).validate(arguments)
                result.append((name, arguments))
            return tuple(result)
        except Exception:
            raise InferenceError(schema_error=True) from None
