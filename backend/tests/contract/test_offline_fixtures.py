"""Local SDK/model interface smoke contracts, not recommendation evaluations."""

import os
import socket
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from tavily import AsyncTavilyClient

from food_recommender.infrastructure.providers.openai import OpenAIStructuredInference


def test_external_connections_are_blocked_before_dns() -> None:
    with pytest.raises(RuntimeError, match="external network"):
        socket.getaddrinfo("api.openai.com", 443)


@pytest.mark.parametrize("method", ["connect", "connect_ex"])
def test_external_ip_connections_are_blocked(method: str) -> None:
    with socket.socket() as connection:
        with pytest.raises(RuntimeError, match="external network"):
            getattr(connection, method)(("203.0.113.1", 443))


@pytest.mark.asyncio
async def test_openai_uses_a_fake_http_response(
    provider_transport: httpx.MockTransport,
) -> None:
    async with httpx.AsyncClient(transport=provider_transport) as client:
        provider = OpenAIStructuredInference(
            client, SecretStr("synthetic-openai-credential"), "gpt-4o-mini"
        )
        response = await provider.generate(
            [{"role": "user", "content": "Fixture request"}], {"type": "object"}
        )
    assert response == '{"status":"fixture"}'


@pytest.mark.asyncio
async def test_tavily_uses_a_fake_http_response(
    provider_transport: httpx.MockTransport,
) -> None:
    async with httpx.AsyncClient(transport=provider_transport) as http:
        client = AsyncTavilyClient(api_key="synthetic-tavily-credential", client=http)
        response = await client.search("fixture culinary concept", max_results=1)
    assert response["results"][0]["url"] == "https://example.test/fixture"


def test_preprovisioned_cpu_models_load_without_downloads() -> None:
    root = os.environ.get("TEST_MODEL_ROOT")
    if root is None:
        if os.environ.get("CI") == "true":
            pytest.fail("CI must provision TEST_MODEL_ROOT; model tests cannot skip")
        pytest.skip(
            "Set TEST_MODEL_ROOT after running scripts/provision_test_models.py"
        )

    import torch
    from transformers import BertModel, CLIPModel

    torch.set_num_threads(1)
    text = BertModel.from_pretrained(Path(root) / "text", local_files_only=True)
    image = CLIPModel.from_pretrained(Path(root) / "image", local_files_only=True)
    with torch.inference_mode():
        text_output = text(input_ids=torch.tensor([[2, 5, 3]]))
        image_output = image(
            input_ids=torch.tensor([[2, 5, 3]]),
            pixel_values=torch.zeros(1, 3, 16, 16),
        )
    assert text_output.last_hidden_state.shape == (1, 3, 384)
    assert image_output.text_embeds.shape == image_output.image_embeds.shape == (1, 512)
    assert torch.isfinite(text_output.last_hidden_state).all()
    assert torch.isfinite(image_output.image_embeds).all()
    assert image.device.type == text.device.type == "cpu"
