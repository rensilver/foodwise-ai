"""Scores export only local measurements and stable associations, with retry deduplication."""

from uuid import uuid4

import pytest

from food_recommender.infrastructure.telemetry.scores import LocalScore, score_payload


def test_score_retry_identity_is_stable_and_content_free():
    score = LocalScore(
        "citation_correctness", 1, uuid4(), "a" * 16, "fixture-ref", uuid4(), 3
    )
    first = score_payload(score)
    assert first == score_payload(score)
    assert first["trace_id"] == score.run.hex
    assert first["observation_id"] == "a" * 16
    assert "comment" not in first
    assert "fixture-ref" not in str(first)


def test_inapplicable_and_invalid_scores_are_not_exported():
    with pytest.raises(ValueError):
        LocalScore("citation_correctness", 1, uuid4(), "a" * 16, "ref", uuid4(), 0)
    with pytest.raises(ValueError):
        LocalScore("citation_correctness", 2, uuid4(), "a" * 16, "ref", uuid4(), 1)


def test_same_score_retry_upserts_one_measurement_and_respects_sampling():
    from food_recommender.infrastructure.telemetry.scores import export_scores

    score = LocalScore(
        "expected_outcome", 1, uuid4(), "a" * 16, "PRIVATE_CANARY_INPUT", uuid4(), 1
    )

    class Client:
        records = {}

        def create_score(self, **payload):
            self.records[payload["score_id"]] = payload

    client = Client()
    assert export_scores(client, [score]) == 1
    assert export_scores(client, [score]) == 1
    assert len(client.records) == 1
    assert "PRIVATE_CANARY" not in str(client.records)
    assert export_scores(client, [score], sample_rate=0) == 0


def test_native_experiment_and_dataset_content_helpers_are_never_invoked():
    import ast
    from pathlib import Path

    root = Path(__file__).parents[2]
    for path in [
        *root.joinpath("src").rglob("*.py"),
        root / "scripts/export_phase10_scores.py",
    ]:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {
                    "run_experiment",
                    "create_dataset",
                    "create_dataset_item",
                    "create_dataset_run_item",
                }, path
