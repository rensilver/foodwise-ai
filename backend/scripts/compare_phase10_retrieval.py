"""Compare fresh retrieval measurements with the initial frozen baseline.

No tuning selection from sparse identity-image labels; retain initial defaults.
"""

import hashlib
import json
from pathlib import Path
from statistics import mean

from food_recommender.agents.prompts import PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[2]


def summarize(report, query_ids):
    results = {}
    for setting in report["summaries"]:
        rows = [
            category
            for row in report["queries"]
            if row["setting"] == setting and row["id"] in query_ids
            for category in row["categories"].values()
        ]
        results[setting] = {
            key: mean(values)
            if (values := [row[key] for row in rows if row[key] is not None])
            else None
            for key in ["recall_at_20", "ndcg_at_5", "cuisine_diversity_at_5"]
        }
    return results


def main():
    baseline_file = ROOT / "evaluation/phase5/comparison_report.json"
    measured_file = ROOT / "evaluation/phase10/retrieval_report.json"
    baseline = json.loads(baseline_file.read_text())
    measured = json.loads(measured_file.read_text())
    assert baseline["source_hashes"] == measured["source_hashes"]
    assert baseline["models"]["text"] == measured["models"]["text"]
    assert baseline["models"]["image"] == measured["models"]["image"]
    assert not any(measured["violations"].values())
    common = {row["id"] for row in baseline["queries"]}
    old, new = summarize(baseline, common), summarize(measured, common)
    report = {
        "baseline_sha256": hashlib.sha256(baseline_file.read_bytes()).hexdigest(),
        "measurement_sha256": hashlib.sha256(measured_file.read_bytes()).hexdigest(),
        "revisions": {
            "prompt_version": PROMPT_VERSION,
            "prompt_sha256": hashlib.sha256(
                (ROOT / "backend/src/food_recommender/agents/prompts.py").read_bytes()
            ).hexdigest(),
            "models": measured["models"],
            "versions": measured["versions"],
        },
        "definitions": {
            "recall_at_20": "Distinct labeled positives retrieved in top 20 / labeled positives; empty labels excluded.",
            "ndcg_at_5": "Binary distinct-positive DCG with log2(rank+1) discount / ideal DCG; empty labels excluded.",
            "cuisine_diversity_at_5": "Distinct nonempty normalized cuisines / returned top-five count; empty results excluded.",
            "aggregation": "Macro mean over query/category pairs, separately for each setting.",
        },
        "common_query_ids": sorted(common),
        "initial_baseline": old,
        "fresh_common_queries": new,
        "deltas": {
            setting: {
                key: new[setting][key] - old[setting][key] for key in old[setting]
            }
            for setting in old
        },
        "all_phase10_queries": measured["summaries"],
        "selection": {
            "text": 0.6,
            "image": 0.4,
            "changed": False,
            "reason": "Sparse positives and exact catalog query images do not justify generalization or tuned defaults; preserve initial weights.",
        },
        "limitations": [
            "Unlabeled items receive zero gain.",
            "Corpus identity images are not unseen user photos.",
            "Deterministic acceptance/provider quality is evaluated separately.",
            "Timings are descriptive local measurements, not statistical performance claims.",
        ],
    }
    target = ROOT / "evaluation/phase10/retrieval_comparison.json"
    target.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"common_queries": len(common), "selection": report["selection"]}))


if __name__ == "__main__":
    main()
