"""Typed schema and safe host/validation responses without inference."""

from fastapi.testclient import TestClient
from test_config import Settings, environment
from test_foundation import FakeReadiness

from food_recommender.api.main import create_app
from food_recommender.application.services import Services


def test_health_and_common_error_contracts_are_described_in_openapi():
    app = create_app(Settings(**environment()), services=Services(FakeReadiness()))
    schema = app.openapi()
    ready = schema["paths"]["/api/v1/health/ready"]["get"]["responses"]
    assert ready["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/HealthResponse"
    )
    assert ready["503"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/HealthResponse"
    )
    for code in ("401", "403", "404", "409", "422", "500"):
        assert code in schema["paths"]["/api/v1/admin/recipes"]["post"]["responses"]
    with TestClient(app, base_url="http://localhost") as client:
        rejected = client.get(
            "/api/v1/health/live", headers={"host": "untrusted.example"}
        )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "invalid_request"
