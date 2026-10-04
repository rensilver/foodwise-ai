import hashlib
import json
from pathlib import Path

from test_text_baseline_labels import strings

ROOT = Path(__file__).resolve().parents[3]


def test_multimodal_labels_preserve_source_and_image_identity():
    labels = json.loads((ROOT / "evaluation/phase5/queries.json").read_text())
    assert len({q["id"] for q in labels["queries"]}) == len(labels["queries"]) == 21
    for filename, expected in labels["source_hashes"].items():
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == expected
    manifest = ROOT / "evaluation/phase0/recipe_media_manifest.json"
    assert (
        hashlib.sha256(manifest.read_bytes()).hexdigest()
        == labels["media_manifest_sha256"]
    )
    image_ids = {str(r["recipe_id"]) for r in json.loads(manifest.read_text())["rows"]}
    for query in labels["queries"]:
        if "image_recipe_id" in query:
            assert query["image_recipe_id"] in image_ids
        supported = {c: set() for c in query["categories"]}
        for evidence in query["evidence"]:
            source = json.loads((ROOT / evidence["file"]).read_text())
            row = next(
                r
                for r in source
                if str(r.get("reviewId", r.get("itemId", r.get("id"))))
                == evidence["record_id"]
            )
            assert all(
                line in strings(row) for line in evidence["excerpt"].splitlines()
            )
            category = (
                "recipe" if evidence["file"] == "data/Recipes.json" else "restaurant"
            )
            supported[category].add(
                str(
                    row["itemId"]
                    if "reviewId" in row
                    else row.get("itemId", row.get("id"))
                )
            )
        assert all(set(ids) <= supported[c] for c, ids in query["relevant"].items())


def test_comparison_report_covers_settings_grounding_and_actual_image_queries():
    directory = ROOT / "evaluation/phase5"
    report = json.loads((directory / "comparison_report.json").read_text())
    labels = json.loads((directory / "queries.json").read_text())
    assert (
        report["labels_sha256"]
        == hashlib.sha256((directory / "queries.json").read_bytes()).hexdigest()
    )
    assert report["source_hashes"] == labels["source_hashes"]
    assert report["media_manifest_sha256"] == labels["media_manifest_sha256"]
    assert set(report["summaries"]) == {
        "text_only",
        "balanced",
        "text_heavy",
        "image_heavy",
        "initial_default",
    }
    assert report["device"] == "cpu"
    assert report["models"]["image"]["dimension"] == 512
    assert report["models"]["text"]["dimension"] == 384
    assert report["association_checks"] == {
        "recipe_images": 109,
        "linked_review_images": 9,
    }
    assert not any(report["violations"].values())
    # Preserve old measurements while accepting reports from the migrated CLI.
    assert report["usage"] in [
        {provider: 0, "trend_searches": 0, "provider_tokens": 0}
        for provider in ("groq_calls", "openai_calls")
    ]
    for setting in report["summaries"]:
        assert {q["id"] for q in report["queries"] if q["setting"] == setting} == {
            q["id"] for q in labels["queries"]
        }
    assert all(
        q["query_recipe_id"] == q["top1_recipe_id"] for q in report["image_only_checks"]
    )
    assert len(report["clip_text_to_image_checks"]) == 3
