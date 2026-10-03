from pathlib import Path

from food_recommender.ingestion.seed import load_seed


def test_complete_committed_seed_plan_preserves_all_identities_and_captions():
    repository = Path(__file__).parents[3]
    plan = load_seed(
        repository / "data",
        repository / "evaluation/phase0/restaurant_reconciliation.json",
    )
    assert len(plan.items) == 323
    assert [item.category for item in plan.items].count("restaurant") == 204
    assert [item.category for item in plan.items].count("recipe") == 109
    assert [item.category for item in plan.items].count("review") == 10
    assert len(plan.issues) == 7 and all(
        issue["status"] == "unresolved" for issue in plan.issues
    )
    assert sum(len(item.documents) for item in plan.items) == 118
    assert len(plan.metadata["duplicate_name_location_groups"]) == 16
    assert sum(len(refs) for refs in plan.review_references.values()) == 9


def test_malformed_json_file_and_missing_captions_are_explicit(tmp_path):
    import json
    import shutil

    repository = Path(__file__).parents[3]
    for name in [
        "structured_restaurant_data.json",
        "Recipes.json",
        "augmented_food_recipe.json",
        "Synthetic-User-Reviews.json",
        "augmented_user_review.json",
        "California-Culinary-Map.txt",
    ]:
        shutil.copy(repository / "data" / name, tmp_path / name)
    (tmp_path / "Recipes.json").write_text("{broken")
    augmented = json.loads((tmp_path / "augmented_user_review.json").read_text())
    augmented[0].pop("image_captions")
    (tmp_path / "augmented_user_review.json").write_text(json.dumps(augmented))
    plan = load_seed(
        tmp_path, repository / "evaluation/phase0/restaurant_reconciliation.json"
    )
    assert not any(item.category == "recipe" for item in plan.items)
    assert sum(item.category == "review" for item in plan.items) == 10
    assert any(
        issue["reason"] == "Malformed JSON record array" for issue in plan.issues
    )
    assert sum("Caption absent" in issue["reason"] for issue in plan.issues) == 2
    assert (
        sum(
            "Enrichment has no accepted base" in issue["reason"]
            for issue in plan.issues
        )
        == 109
    )


def test_identical_review_captions_keep_both_media_associations(tmp_path):
    import hashlib

    from test_ingestion_images import png

    from food_recommender.domain.catalog import SourceData
    from food_recommender.ingestion.adapters import adapt_review, digest
    from food_recommender.ingestion.images import prepare_image
    from food_recommender.ingestion.models import SeedItem
    from food_recommender.ingestion.seed import (
        attach_image,
        caption_document,
        source_record,
    )

    source = SourceData(
        id="source",
        logical_source_id="course-reviews",
        locator_kind="file",
        locator="reviews",
        content_hash="a" * 64,
    )
    record = source_record(
        source, "review", "9", raw={"image_captions": ["Bowl", "Bowl"]}
    )
    item = SeedItem(
        adapt_review(
            {"reviewId": 9, "itemId": 5, "userId": "demo", "text": "Nice"}, "reviews"
        ).data,
        (source,),
        (record,),
        (
            caption_document(record, "Bowl", reference="url1"),
            caption_document(record, "Bowl", reference="url2"),
        ),
    )
    for index in range(2):
        image = prepare_image(png(), tmp_path, namespace=str(index))
        locator = f"https://example.org/{index}.png"
        image_source = SourceData(
            id=digest(locator),
            logical_source_id="course-reviews",
            locator_kind="url",
            locator=locator,
            content_hash=hashlib.sha256(png()).hexdigest(),
        )
        item = attach_image(
            item,
            image,
            locator,
            image_source,
            image_record_id=f"9:{index}",
            caption_text="Bowl",
        )
    assert len(item.media) == len(item.documents) == 2
    assert {doc.media_id for doc in item.documents} == {
        media.id for media in item.media
    }
    assert all(
        rec["raw_payload"]["caption_source_record"] == record["id"]
        for rec in item.records[1:]
    )
