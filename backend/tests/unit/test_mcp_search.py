import pytest
from pydantic import ValidationError

from food_recommender.domain.values import Category
from food_recommender.mcp.schemas import SearchRequest


def test_search_limits_filters_and_injection_fields():
    for values in (
        {"query": "food", "limit": 21},
        {"query": "food", "sql": "DELETE"},
        {"query": "food", "path": "/etc/passwd"},
        {"query": "food", "limit": True},
    ):
        with pytest.raises(ValidationError):
            SearchRequest(**values)
    request = SearchRequest(
        query="x'; DROP TABLE recipes; --", location="California", max_price_band=2
    )
    plan = request.plan(Category.RECIPE)
    assert plan.query == request.query
    assert plan.location is None and plan.max_price_band is None
    assert request.plan(Category.RESTAURANT).location == "California"
