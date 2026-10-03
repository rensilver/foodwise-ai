import pytest

from food_recommender.ingestion.adapters import SourceError
from food_recommender.ingestion.merge import merge_records


def test_identity_join_preserves_sources_and_order_independently():
    base = [{"id": 1, "name": "Soup"}, {"id": 2, "name": "Pizza"}]
    enriched = [
        {"id": 2, "name": "Pizza", "image_description": "Round"},
        {"id": 1, "name": "Soup", "image_description": "Bowl"},
    ]
    result = merge_records(
        base,
        enriched,
        identity="id",
        enrichment={"image_description"},
        base_source="base",
        augmented_source="aug",
    )
    assert len(result) == 2
    assert result[0].payload == {"id": 1, "name": "Soup", "image_description": "Bowl"}
    assert result[0].sources == (("base", base[0]), ("aug", enriched[1]))


@pytest.mark.parametrize(
    "aug",
    [
        [{"id": 1, "name": "Changed"}],
        [{"id": 2, "name": "Extra"}],
        [{"id": 1, "name": "Soup"}, {"id": 1, "name": "Soup"}],
        [{"id": 1, "name": "Soup", "secret_extra": "x"}],
    ],
)
def test_rejects_silent_overwrites_or_identity_errors(aug):
    with pytest.raises(SourceError, match="aug"):
        merge_records(
            [{"id": 1, "name": "Soup"}],
            aug,
            identity="id",
            enrichment={"image_description"},
            base_source="base",
            augmented_source="aug",
        )


def test_missing_enrichment_retains_base():
    result = merge_records(
        [{"reviewId": 1, "text": "Fine"}],
        [],
        identity="reviewId",
        enrichment={"image_captions"},
        base_source="base",
        augmented_source="aug",
    )
    assert result[0].payload == {"reviewId": 1, "text": "Fine"}
