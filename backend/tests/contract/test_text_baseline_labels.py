"""Committed labels must retain source evidence and reported grounding checks."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for item in value for s in strings(item)]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings(item)]
    return []


def test_every_baseline_label_has_matching_source_identity_hash_and_excerpt():
    labels = json.loads((ROOT / "evaluation/phase4/text_queries.json").read_text())
    assert len({q["id"] for q in labels["queries"]}) == len(labels["queries"]) == 17
    for filename, expected in labels["source_hashes"].items():
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == expected
    for query in labels["queries"]:
        assert bool(query["relevant_ids"]) == (query["expected_status"] == "success")
        supported_ids = set()
        for evidence in query["evidence"]:
            source = json.loads((ROOT / evidence["file"]).read_text())
            row = next(
                row
                for row in source
                if str(row.get("reviewId", row.get("itemId", row.get("id"))))
                == evidence["record_id"]
            )
            assert all(
                line in strings(row) for line in evidence["excerpt"].splitlines()
            )
            supported_ids.add(
                str(
                    row["itemId"]
                    if "reviewId" in row
                    else row.get("itemId", row.get("id"))
                )
            )
        assert set(query["relevant_ids"]) <= supported_ids


def test_report_matches_versioned_labels_and_has_zero_grounding_violations():
    directory = ROOT / "evaluation/phase4"
    report = json.loads((directory / "baseline_report.json").read_text())
    labels = json.loads((directory / "text_queries.json").read_text())
    assert (
        report["labels_sha256"]
        == hashlib.sha256((directory / "text_queries.json").read_bytes()).hexdigest()
    )
    assert report["source_hashes"] == labels["source_hashes"]
    assert not any(report["violations"].values())
    assert report["dimension"] == 384 and report["device"] == "cpu"
    # Preserve old measurements while accepting reports from the migrated CLI.
    assert report["usage"] in [
        {provider: 0, "trend_searches": 0, "provider_tokens": 0}
        for provider in ("groq_calls", "openai_calls")
    ]
    assert {row["id"] for row in report["queries"]} == {
        q["id"] for q in labels["queries"]
    }
