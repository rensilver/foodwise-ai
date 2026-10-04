"""Groq structured generation boundary; independent text/vision configuration."""

import asyncio
from typing import Any

import httpx
from pydantic import SecretStr


class GroqStructuredInference:
    def __init__(
        self,
        client: httpx.AsyncClient,
        api_key: SecretStr,
        model: str,
        semaphore: asyncio.Semaphore | None = None,
    ) -> None:
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
        async with self.semaphore:
            response = await self.client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key.get_secret_value()}"},
                json={
                    "model": self.model,
                    "messages": request_messages,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "culinary_extraction",
                            "strict": False,
                            "schema": schema,
                        },
                    },
                    "stream": False,
                    "max_completion_tokens": 4096,
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Missing structured response")
            return content
