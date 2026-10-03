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
