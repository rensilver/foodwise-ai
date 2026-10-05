"""Local fixture scores with optional synthetic Cloud export; fixture data stays local."""

import argparse
import asyncio
import json
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from dotenv import dotenv_values
from scripts.phase10_acceptance import audit_state, load_labels
from scripts.phase10_tracing import CaptureExporter, bounded_sdk_call, traced_case

from food_recommender.infrastructure.observability import configure_logging
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing, sdk_factory
from food_recommender.infrastructure.telemetry.scores import (
    DEFINITIONS,
    EVALUATOR_REVISION,
    LocalScore,
    export_scores,
    score_payload,
)

ROOT = Path(__file__).resolve().parents[2]


async def evaluate(tracing, capture, *, flush=True):
    execution = uuid4()
    rows = []
    scores = []
    runs = []
    for case in load_labels()["cases"]:
        states, refs = await traced_case(case, tracing)
        runs.extend(refs)
        if flush:
            assert bounded_sdk_call(tracing.client.flush, seconds=30), (
                "Score flush deadline"
            )
        for index, (state, ref, turn) in enumerate(
            zip(states, refs, case["turns"], strict=True)
        ):
            root = next(
                span
                for span in capture.spans
                if f"{span.context.trace_id:032x}" == ref
                and span.name == "recommend-food"
            )
            final = (state.get("final") or {}).get("result", {})
            recommendations = final.get("recommendations", [])
            actual = (
                "clarification"
                if state["profile"].get("clarification")
                else "recommendations"
                if recommendations
                else "abstention"
                if (state.get("final") or {}).get("status") == "success"
                else "failure"
            )
            violations = audit_state(state)
            fixture = f"{case['id']}:{index}"
            scores.append(
                LocalScore(
                    "expected_outcome",
                    int(actual == turn["expected"]),
                    UUID(ref),
                    f"{root.context.span_id:016x}",
                    fixture,
                    execution,
                    1,
                )
            )
            count = len(recommendations)
            synth = next(
                (
                    span
                    for span in capture.spans
                    if f"{span.context.trace_id:032x}" == ref
                    and span.name == "synthesize-recommendations"
                ),
                None,
            )
            if count and synth:
                observation = f"{synth.context.span_id:016x}"
                citations = sum(len(item["citation_ids"]) for item in recommendations)
                if citations:
                    scores.append(
                        LocalScore(
                            "citation_correctness",
                            1 - violations["fabricated_citations"] / citations,
                            UUID(ref),
                            observation,
                            fixture,
                            execution,
                            citations,
                        )
                    )
                scores.append(
                    LocalScore(
                        "fabricated_ids",
                        violations["fabricated_recommendations"],
                        UUID(ref),
                        observation,
                        fixture,
                        execution,
                        count,
                    )
                )
                hard = any(
                    item["strength"] == "hard"
                    for item in state["profile"]["preferences"]["constraints"]
                )
                if hard:
                    scores.append(
                        LocalScore(
                            "hard_constraint_violations",
                            violations["hard_constraint_violations"],
                            UUID(ref),
                            observation,
                            fixture,
                            execution,
                            count,
                        )
                    )
            assert not any(violations.values()) and actual == turn["expected"]
            rows.append(
                {
                    "fixture": case["id"],
                    "turn": index,
                    "actual": actual,
                    "violations": violations,
                }
            )
    return scores, rows, runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-cloud", action="store_true")
    args = parser.parse_args()
    configure_logging()
    values = (
        {
            k: v
            for k, v in dotenv_values(ROOT / ".env").items()
            if k.startswith("LANGFUSE_")
        }
        if args.enable_cloud
        else {
            "LANGFUSE_BASE_URL": "https://us.cloud.langfuse.com",
            "LANGFUSE_PUBLIC_KEY": uuid4().hex,
            "LANGFUSE_SECRET_KEY": "offline",
        }
    )
    values.update(
        LANGFUSE_ENABLED=True,
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
        LANGFUSE_CORRELATION_KEY=uuid4().hex,
    )
    settings = TelemetrySettings(**values)
    capture = CaptureExporter()
    # Offline captures only sanitized spans; Cloud uses the same SDK exporter.
    tracing = LazyTracing(
        settings,
        factory=(lambda s: sdk_factory(s))
        if args.enable_cloud
        else (lambda s: sdk_factory(s, capture)),
        revisions={
            "prompt_revision": "phase10-synthetic-v1",
            "dataset_revision": "phase10-v1",
        },
    )
    if args.enable_cloud:
        # Observe sanitized spans without replacing the Cloud export destination.
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor

        tracing.initialize()
        tracing.client._resources.tracer_provider.add_span_processor(
            SimpleSpanProcessor(capture)
        )
    scores, rows, runs = asyncio.run(
        evaluate(tracing, capture, flush=not args.enable_cloud)
    )
    if args.enable_cloud:
        export_scores(tracing.client, scores)
        export_scores(
            tracing.client, scores
        )  # Deliberate same-ID retry for stored dedup audit.
        path = ROOT / ".local-tmp/langfuse-audit-private.json"
        old = json.loads(path.read_text()) if path.exists() else {"trace_ids": []}
        old["trace_ids"].extend(runs)
        old["score_ids"] = [score_payload(score)["score_id"] for score in scores]
        path.write_text(json.dumps(old, indent=2) + "\n")
        assert bounded_sdk_call(tracing.client.flush, seconds=30), (
            "Score flush deadline"
        )
    cloud_audit = None
    if args.enable_cloud:
        expected = {
            score_payload(score)["score_id"]: score_payload(score) for score in scores
        }
        deadline = time.monotonic() + 90
        with httpx.Client(
            base_url=settings.base_url,
            auth=(
                settings.public_key.get_secret_value(),
                settings.secret_key.get_secret_value(),
            ),
            timeout=5,
        ) as http:
            while True:
                response = http.get(
                    "/api/public/v3/scores",
                    params={
                        "id": ",".join(expected),
                        "fields": "details,subject",
                        "limit": 100,
                    },
                )
                response.raise_for_status()
                stored = response.json()["data"]
                if len(stored) == len(expected) or time.monotonic() >= deadline:
                    break
                time.sleep(3)
        failures = []
        if len(stored) != len(expected) or len({s["id"] for s in stored}) != len(
            expected
        ):
            failures.append("score_count_or_duplicate")
        for score in stored:
            want = expected.get(score["id"])
            if (
                not want
                or score["value"] != want["value"]
                or score["name"] != want["name"]
            ):
                failures.append("metric_value")
                continue
            subject = score.get("subject") or {}
            if (
                subject.get("id") != want["observation_id"]
                or subject.get("traceId") != want["trace_id"]
            ):
                failures.append("observation_association")
            if score.get("comment") or score.get("metadata") != want["metadata"]:
                failures.append("content_or_metadata")
        cloud_audit = {
            "api": "Scores v3",
            "expected_unique": len(expected),
            "stored_unique": len(stored),
            "same_id_exports": 2,
            "failures": sorted(set(failures)),
            "passed": not failures,
        }
    report = {
        "date": "2026-10-05",
        "mode": "synthetic Cloud" if args.enable_cloud else "offline fake exporter",
        "definitions": DEFINITIONS,
        "evaluator_revision": EVALUATOR_REVISION,
        "scores": [score_payload(score) for score in scores],
        "local_results": rows,
        "inapplicable": "no denominator means omitted; never replaced with zero",
        "experiment_helpers": "disabled; no run_experiment or hosted datasets",
        "remote_fixture_content": False,
        "sample_rate": 1,
        "cloud_audit": cloud_audit,
    }
    # Opaque export associations are retained only in ignored private output.
    (ROOT / ".local-tmp/phase10-score-payloads.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    report["scores"] = [
        {
            k: v
            for k, v in score_payload(score).items()
            if k in {"name", "value", "data_type"}
        }
        for score in scores
    ]
    (ROOT / "evaluation/phase10/score_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    bounded_sdk_call(tracing.client.shutdown)
    print(
        json.dumps(
            {"scores": len(scores), "turns": len(rows), "cloud": args.enable_cloud}
        )
    )


if __name__ == "__main__":
    main()
