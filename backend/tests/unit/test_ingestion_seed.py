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
