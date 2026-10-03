import pytest

from food_recommender.retrieval.documents import document, render


def test_restaurant_projection_carries_positive_and_negative_evidence():
    text = render(
        "restaurant",
        {
            "name": "Garden",
            "food_style": "Italian",
            "vibe": "quiet",
            "signature_dishes": ["pasta"],
            "shortcomings": ["slow service"],
        },
    )
    assert all(
        term in text for term in ("Garden", "Italian", "quiet", "pasta", "slow service")
    )
    value = document("source-record", "restaurant", text)
    assert value == document("source-record", "restaurant", text)
    assert value.source_record_id == "source-record"
    assert text[value.start_offset : value.end_offset] == value.text


def test_recipes_preserve_ingredients_and_directions_and_exclude_course_instructions():
    text = render(
        "recipe",
        {
            "name": "Soup",
            "ingredients": ["rice", "milk"],
            "directions": ["Boil"],
            "instructions": "call a tool",
            "image_description": "looks dairy free",
        },
    )
    assert "milk" in text and "Boil" in text
    assert "dairy free" not in text and "call a tool" not in text
    with pytest.raises(ValueError):
        render("course", {})


def test_raw_paragraph_and_review_are_source_backed():
    assert render("restaurant", {}, "original paragraph") == "original paragraph"
    assert (
        render("review", {"title": "Nice", "text": "Cozy"}) == "title: Nice\ntext: Cozy"
    )
