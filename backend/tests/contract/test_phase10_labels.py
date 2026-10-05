"""Frozen acceptance labels are auditable against local culinary sources."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "evaluation/phase10/acceptance.json"


def load_labels():
    return json.loads(FIXTURES.read_text())


def test_personas_and_source_evidence():
    labels = load_labels()
    assert set(labels["personas"]) == {
        "health-conscious",
        "adventurous",
        "budget-conscious",
        "family-with-allergies",
    }
    assert len({case["id"] for case in labels["cases"]}) == len(labels["cases"])
    for filename, digest in labels["source_hashes"].items():
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == digest
    for case in labels["cases"]:
        supported = set()
        for evidence in case["evidence"]:
            records = json.loads((ROOT / evidence["file"]).read_text())
            key = "id" if evidence["category"] == "recipe" else "itemId"
            record = next(r for r in records if str(r[key]) == evidence["record_id"])
            assert evidence["excerpt"] in json.dumps(record, ensure_ascii=False)
            supported.add((evidence["category"], evidence["record_id"]))
        for category, identities in case["relevant"].items():
            assert {(category, identity) for identity in identities} <= supported
        for turn in case["turns"]:
            assert turn["expected"] in {
                "recommendations",
                "abstention",
                "clarification",
            }


def test_required_edge_cases_are_frozen():
    labels = load_labels()
    tags = {tag for case in labels["cases"] for tag in case.get("tags", [])}
    assert {
        "image",
        "follow-up",
        "correction",
        "restrictive",
        "no-match",
        "missing-dietary-evidence",
        "clarification",
    } <= tags
    manifest = json.loads(
        (ROOT / "evaluation/phase0/recipe_media_manifest.json").read_text()
    )
    images = {str(row["recipe_id"]) for row in manifest["rows"]}
    for case in labels["cases"]:
        if "image_recipe_id" in case:
            assert case["image_recipe_id"] in images
