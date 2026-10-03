import json

import pytest

from food_recommender.ingestion.extraction import ExtractionService, RestaurantFields


class Provider:
    model = "configured-model"

    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def generate(self, messages, schema, *, image=None):
        self.calls.append((messages, schema, image))
        return next(self.outputs)


@pytest.mark.asyncio
async def test_validation_repairs_and_preview_does_not_persist(tmp_path):
    provider = Provider(
        ["bad json", '{"name":"Soup","rating":10}', '{"name":"Soup","rating":4}']
    )
    service = ExtractionService(provider, tmp_path)
    result = await service.preview(
        "untrusted source", RestaurantFields, source="input", record_id="1"
    )
    assert result.status == "validated"
    assert result.attempts == 3
    assert result.fields["rating"] == 4
    assert list(tmp_path.iterdir()) == []
    assert "untrusted" in provider.calls[0][0][0]["content"]


@pytest.mark.asyncio
async def test_exhaustion_quarantines_source_and_never_returns_defaults(tmp_path):
    provider = Provider(["{}"] * 3)
    result = await ExtractionService(provider, tmp_path).extract(
        "source text", RestaurantFields, source="map.txt", record_id="26"
    )
    assert result.status == "quarantined"
    assert result.fields is None
    assert len(provider.calls) == 3
    saved = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert saved["source"] == "map.txt" and saved["record_id"] == "26"
    assert saved["raw_text"] == "source text"


@pytest.mark.asyncio
async def test_provider_failure_is_typed_and_redacted(tmp_path):
    class Broken(Provider):
        async def generate(self, *args, **kwargs):
            raise RuntimeError("secret-canary")

    result = await ExtractionService(Broken([]), tmp_path).preview(
        "text", RestaurantFields, source="x", record_id="y"
    )
    assert result.status == "provider_unavailable"
    assert "secret-canary" not in repr(result)


@pytest.mark.asyncio
async def test_groq_request_contract_preserves_model_and_has_no_tools():
    import httpx
    from pydantic import SecretStr

    from food_recommender.infrastructure.groq_ingestion import GroqStructuredInference

    def respond(request):
        body = json.loads(request.content)
        assert body["model"] == "configured-model"
        assert body["response_format"]["type"] == "json_schema"
        assert body["stream"] is False and "tools" not in body
        return httpx.Response(
            200, json={"choices": [{"message": {"content": '{"name":"Soup"}'}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await ExtractionService(
            GroqStructuredInference(client, SecretStr("synthetic"), "configured-model"),
            None,
        ).preview("Soup", RestaurantFields, source="input", record_id="1")
        assert result.status == "validated"
