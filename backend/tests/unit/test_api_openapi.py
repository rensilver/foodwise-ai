"""SSE and shared expert contracts are generated from the same runtime types."""

from test_config import Settings, environment
from test_foundation import FakeReadiness

from food_recommender.api.main import create_app
from food_recommender.application.services import Services


def test_sse_openapi_has_all_events_evidence_and_expert_outcomes():
    schema = create_app(
        Settings(**environment()), services=Services(FakeReadiness())
    ).openapi()
    response = schema["paths"]["/api/v1/conversations/{conversation_id}/messages"][
        "post"
    ]["responses"]["200"]
    assert "text/event-stream" in response["content"]
    types = schema["components"]["schemas"]
    assert "StreamContract" in types
    for name in (
        "ProgressEvent",
        "ClarificationEvent",
        "RecommendationsEvent",
        "ErrorEvent",
        "DoneEvent",
        "CandidateEvidence",
        "Citation",
        "TrendAnalysis",
        "NutritionAnalysis",
        "StyleAnalysis",
    ):
        assert name in types
    assert "evidence" in types["RecommendationsEvent"]["properties"]
