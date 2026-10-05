import pytest

from food_recommender.retrieval.models import TextPlan


@pytest.mark.parametrize(
    "changes",
    [
        {"limit": 0},
        {"limit": 21},
        {"limit": True},
        {"query": " "},
        {"query": "x" * 2001},
        {"sources": ("review",)},
        {"max_price_band": 5},
        {"sources": ("sql",)},
        {"categories": ()},
    ],
)
def test_plan_rejects_invalid_limits_and_unscoped_reviews(changes):
    values = {"query": "pizza", **changes}
    with pytest.raises(ValueError):
        TextPlan(**values)


def test_request_schema_rejects_unknown_fields_and_outcome_roundtrips():
    from food_recommender.application.recommendations.contracts import (
        contract_json_schema,
        text_retrieval_adapter,
    )
    from food_recommender.retrieval.outcomes import TextRetrievalOutcome

    schema = contract_json_schema(text_retrieval_adapter)
    assert schema["additionalProperties"] is False
    value = TextRetrievalOutcome("no_results", (), "model", "revision", 1.0)
    assert (
        text_retrieval_adapter.validate_json(text_retrieval_adapter.dump_json(value))
        == value
    )
