"""Release evidence must reject degraded experts and fabricated citations."""

import copy
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/phase11_live_demo.py"


def load():
    spec = importlib.util.spec_from_file_location("phase11_live_demo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state():
    return {
        "lifecycle": "completed",
        "metrics": {
            "stages": [
                {"stage": name, "status": "success"}
                for name in (
                    "profile",
                    "retrieval",
                    "trend",
                    "style",
                    "nutrition",
                    "recommendation",
                )
            ]
        },
        "catalog": [
            {
                "evidence": {
                    "entity": {"category": "recipe", "id": "1"},
                    "citations": [{"id": "catalog-1"}],
                },
                "text_cosine_similarity": 0.8,
                "image_cosine_similarity": 0.9,
            }
        ],
        "trend": {
            "status": "success",
            "result": {
                "claims": [
                    {
                        "claim": "Popular seasonal pizza",
                        "citations": [
                            {
                                "id": "web-1",
                                "url": "https://example.com/food",
                                "published_on": "2026-10-01",
                                "retrieved_at": "2026-10-06T12:00:00Z",
                            }
                        ],
                    }
                ]
            },
        },
        "style": {"status": "success"},
        "nutrition": {"status": "success"},
        "final": {
            "status": "success",
            "result": {
                "recommendations": [
                    {
                        "entity": {"category": "recipe", "id": "1"},
                        "citation_ids": ["catalog-1"],
                    }
                ]
            },
        },
    }


def test_accepts_complete_evidence():
    assert all(load().checks(state(), image=True, today="2026-10-06").values())


@pytest.mark.parametrize(
    "change",
    ["degraded", "fabricated", "uncited", "stale", "no_image", "repeat_synthesis"],
)
def test_rejects_incomplete_evidence(change):
    value = copy.deepcopy(state())
    if change == "degraded":
        value["style"]["status"] = "unavailable"
    elif change == "fabricated":
        value["final"]["result"]["recommendations"][0]["entity"]["id"] = "999"
    elif change == "uncited":
        value["final"]["result"]["recommendations"][0]["citation_ids"] = []
    elif change == "stale":
        value["trend"]["result"]["claims"][0]["citations"][0]["published_on"] = (
            "2020-01-01"
        )
    elif change == "no_image":
        value["catalog"][0]["image_cosine_similarity"] = None
    else:
        value["metrics"]["stages"].append(
            {"stage": "recommendation", "status": "success"}
        )
    assert not all(load().checks(value, image=True, today="2026-10-06").values())


def test_rejects_a_trend_claim_without_dated_citations():
    value = state()
    value["trend"]["result"]["claims"][0]["citations"] = []
    assert not load().checks(value, image=True, today="2026-10-06")[
        "dated_trend_claims"
    ]


def test_dependency_order_requires_overlap_and_a_single_join():
    module = load()
    spans = [
        {"stage": "profile", "start": 0, "end": 1},
        {"stage": "retrieval", "start": 1, "end": 2},
        {"stage": "trend", "start": 2, "end": 6},
        {"stage": "style", "start": 2.1, "end": 5},
        {"stage": "nutrition", "start": 2.2, "end": 4},
        {"stage": "recommendation", "start": 6, "end": 7},
    ]
    assert module.order_checks(spans)
    sequential = copy.deepcopy(spans)
    sequential[4].update(start=5, end=6)
    assert not module.order_checks(sequential)
    early_join = copy.deepcopy(spans)
    early_join[-1]["start"] = 5
    assert not module.order_checks(early_join)
    assert not module.order_checks(spans + [spans[-1]])


def test_failed_setup_cannot_reuse_a_previous_passing_report(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys

    script = SCRIPT.parents[1].parent / "infra/verify_live_demo.py"
    spec = importlib.util.spec_from_file_location("verify_live_demo", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    for relative in (
        "infra/verify_live_demo.py",
        "backend/scripts/phase11_live_demo.py",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("fixture")
    output = tmp_path / "report.json"
    output.write_text(json.dumps({"passed": True, "turns": [1, 2, 3, 4]}))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify",
            "--enable-live",
            "--env-file",
            str(output),
            "--minilm-root",
            str(tmp_path),
            "--clip-root",
            str(tmp_path),
            "--review-cache",
            str(tmp_path),
            "--output",
            str(output),
        ],
    )

    def command(args, **kwargs):
        if args[0] == "git":
            return "fixture-revision\n"
        raise subprocess.CalledProcessError(7, args)

    monkeypatch.setattr(module.subprocess, "check_output", command)
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 1),
    )
    with pytest.raises(subprocess.CalledProcessError):
        module.main()
    report = json.loads(output.read_text())
    assert report["passed"] is False
    assert report["turns"] == []
    assert report["isolation"]["owner_containers_unchanged"] is False
    assert not list(tmp_path.rglob("*.env"))


def test_missing_outcomes_are_recorded_as_failed_checks():
    value = state()
    value.update(final=None, trend=None, style=None, nutrition=None)
    assert not all(load().checks(value, image=True, today="2026-10-06").values())
