"""Opt-in purge of journaled/tombstoned or locally recorded synthetic traces only."""

import argparse
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import dotenv_values

from food_recommender.infrastructure.telemetry.ledger import TraceLedger

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-cloud", action="store_true")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--deadline-seconds", type=int, default=180)
    args = parser.parse_args()
    if not args.enable_cloud:
        parser.error("Remote deletion requires --enable-cloud")
    ledger = TraceLedger(args.ledger) if args.ledger else None
    private = (
        json.loads((ROOT / ".local-tmp/langfuse-audit-private.json").read_text())
        if ledger is None
        else {}
    )
    identities = sorted(set(ledger.pending() if ledger else private["trace_ids"]))
    assert all(
        len(identity) == 32 and all(c in "0123456789abcdef" for c in identity)
        for identity in identities
    )
    values = dotenv_values(ROOT / ".env")
    start = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    end = datetime.now(UTC).isoformat()
    filters = [
        {
            "type": "stringOptions",
            "column": "traceId",
            "operator": "any of",
            "value": identities,
        },
        {"type": "datetime", "column": "startTime", "operator": ">=", "value": start},
        {"type": "datetime", "column": "startTime", "operator": "<=", "value": end},
    ]
    observed_remaining = None
    score_remaining = None
    checks = 0
    with httpx.Client(
        base_url=values["LANGFUSE_BASE_URL"],
        auth=(values["LANGFUSE_PUBLIC_KEY"], values["LANGFUSE_SECRET_KEY"]),
        timeout=5,
    ) as client:
        if identities:
            response = client.request(
                "DELETE", "/api/public/traces", json={"traceIds": identities}
            )
            response.raise_for_status()
            deadline = time.monotonic() + args.deadline_seconds
            while True:
                response = client.get(
                    "/api/public/v2/observations",
                    params={
                        "filter": json.dumps(filters),
                        "fields": "core",
                        "limit": 1,
                    },
                )
                response.raise_for_status()
                observed_remaining = bool(response.json()["data"])
                checks += 1
                if not observed_remaining or time.monotonic() >= deadline:
                    break
                time.sleep(10)
            score_ids = private.get("score_ids", [])
            if score_ids:
                response = client.get(
                    "/api/public/v3/scores",
                    params={"id": ",".join(score_ids), "limit": 1},
                )
                response.raise_for_status()
                score_remaining = bool(response.json()["data"])
            if ledger and not observed_remaining:
                for trace in identities:
                    ledger.confirm(trace)
    report = {
        "date": "2026-10-05",
        "region": "US",
        "submitted_trace_ids": len(identities),
        "scope": "known local synthetic references"
        if ledger is None
        else "durable tombstoned traces",
        "observation_readback_api": "v2 with explicit trace-ID filter and bounded time window",
        "score_readback_api": "v3",
        "remaining_observations": observed_remaining,
        "remaining_scores": score_remaining,
        "polls": checks,
        "passed": observed_remaining is False and score_remaining is not True,
        "normal_conversation_export": False,
        "limitations": [
            "Deletion is asynchronous and there is no provider completion notification",
            "This recent synthetic window does not verify older Hobby data beyond the access window",
            "Cloud backups and extended delayed-ingestion behavior are not independently verified",
            "Normal conversation export remains disabled; manual purge/retry is developer tooling",
        ],
    }
    (ROOT / "evaluation/phase10/langfuse_purge_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "submitted": len(identities),
                "remaining_observations": observed_remaining,
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
