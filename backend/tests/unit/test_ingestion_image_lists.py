import pytest

from food_recommender.ingestion.adapters import SourceError
from food_recommender.ingestion.image_lists import parse_images


def test_legacy_list_and_native_list():
    assert parse_images("['https://example.org/a.png']", "reviews.json", 9) == (
        "https://example.org/a.png",
    )
    assert parse_images([], "reviews.json", 9) == ()
    assert parse_images(None, "reviews.json", 9) == ()


@pytest.mark.parametrize(
    "value",
    [
        "__import__('os').system('true')",
        "[1]",
        "'string'",
        "{'x': 1}",
        "[",
        [None],
        "x" * 16385,
        ["x"] * 21,
        ["a", "a"],
        [""],
        [[["deep"]]],
    ],
)
def test_malformed_oversized_and_duplicate_references(value):
    with pytest.raises(SourceError, match="reviews.json record 9"):
        parse_images(value, "reviews.json", 9)
