from dataclasses import asdict

import pytest

from food_recommender.ingestion.adapters import (
    SourceError,
    adapt_recipe,
    adapt_restaurant,
    adapt_review,
)


def test_restaurant_preserves_identity_raw_unknowns_and_normalizes():
    raw = {
        "itemId": 1000001,
        "name": "  Café  ",
        "food_style": "Modern ITALIAN",
        "location": " Silver Lake ",
        "price_range": 2,
        "extra": "retained",
    }
    result = adapt_restaurant(raw, "restaurants.json")
    assert result.data.id == "1000001"
    assert result.data.cuisine == "Modern ITALIAN"
    assert result.data.normalized_cuisine == "modern italian"
    assert result.data.normalized_location == "silver lake"
    assert result.raw == raw
    assert result.data.allergens is None
    assert result.data.latitude is None


def test_recipe_time_and_complete_ingredients():
    result = adapt_recipe(
        {
            "id": 1,
            "name": "Soup",
            "prep_time": "1 hr 20 mins",
            "ingredients": ["salt", "peanuts"],
        },
        "recipes.json",
    )
    assert result.data.id == "1"
    assert result.data.prep_time == "PT80M"
    assert result.data.ingredients == ("salt", "peanuts")
    assert result.raw["prep_time"] == "1 hr 20 mins"
    assert result.data.nutrition is None


def test_review_keeps_foreign_id_and_date():
    result = adapt_review(
        {
            "reviewId": 9,
            "itemId": 1000001,
            "userId": "demo",
            "text": "Nice",
            "date": "2025-11-15",
        },
        "reviews.json",
    )
    assert asdict(result.data)["restaurant_id"] == "1000001"
    assert result.data.published_on.isoformat() == "2025-11-15"


@pytest.mark.parametrize(
    "raw",
    [
        {"id": True, "name": "x"},
        {"id": 1, "name": ""},
        {"id": 1, "name": "x", "servings": -1},
        {"id": 1, "name": "x", "prep_time": "eventually"},
    ],
)
def test_source_specific_validation(raw):
    with pytest.raises(SourceError, match="recipes.json"):
        adapt_recipe(raw, "recipes.json")
