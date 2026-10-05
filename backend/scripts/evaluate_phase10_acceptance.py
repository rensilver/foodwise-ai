"""Reproducible offline acceptance report with source/code/model revision bindings."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from phase10_acceptance import LABELS, ROOT, execute_case, load_labels

from food_recommender.agents.prompts import PROMPT_VERSION
from food_recommender.retrieval.embedding_contracts import (
    CLIP_MODEL,
    CLIP_REVISION,
    MINILM_MODEL,
    MINILM_REVISION,
)


def revisions():
    paths = [
        *sorted((ROOT / "backend/src/food_recommender/agents").rglob("*.py")),
        *sorted(
            (ROOT / "backend/src/food_recommender/application/recommendations").glob(
                "*.py"
            )
        ),
        ROOT / "backend/scripts/phase10_acceptance.py",
    ]
    return {
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "labels_sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest(),
        "source_hashes": load_labels()["source_hashes"],
        "implementation_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
        "prompt_version": PROMPT_VERSION,
        "inference": {"implementation": "FixtureInference", "remote_model": None},
        "embeddings": {
            "text": {
                "model": MINILM_MODEL,
                "revision": MINILM_REVISION,
                "dimension": 384,
            },
            "image": {"model": CLIP_MODEL, "revision": CLIP_REVISION, "dimension": 512},
            "executed": False,
        },
        "packages": {
            name: importlib.metadata.version(name)
            for name in ["langgraph", "pydantic", "httpx"]
        },
    }


async def evaluate(output):
    rows = []
    for case in load_labels()["cases"]:
        states, inference, tools = await execute_case(case)
        turns = []
        for turn, state in zip(case["turns"], states, strict=True):
            final = state.get("final") or {}
            items = final.get("result", {}).get("recommendations", [])
            actual = (
                "clarification"
                if state["profile"].get("clarification")
                else "recommendations"
                if items
                else "abstention"
                if final.get("status") == "success"
                else "failure"
            )
            assert actual == turn["expected"], f"Unexpected outcome for {case['id']}"
            turns.append(
                {
                    "expected": turn["expected"],
                    "actual": actual,
                    "recommendations": items,
                    "limitations": final.get("result", {}).get("limitations", []),
                    "metrics": state["metrics"],
                }
            )
        rows.append(
            {
                "id": case["id"],
                "persona": case["persona"],
                "turns": turns,
                "inference_calls": len(inference.calls),
                "tool_calls": len(tools.calls),
            }
        )
    report = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "mode": "offline fake boundaries, real six-agent graph",
        "revisions": revisions(),
        "cases": rows,
        "paid_provider_calls": 0,
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"Recorded {len(rows)} cases / {sum(len(row['turns']) for row in rows)} turns"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation/phase10/acceptance_report.json",
    )
    asyncio.run(evaluate(parser.parse_args().output))
