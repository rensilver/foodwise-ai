"""Opt-in P11-11/12 synthetic Cloud audit; no fixture content or paid inference."""

import argparse
import asyncio
import base64
import json
import re
import time
import traceback
from collections import Counter
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

import httpx
import requests
from dotenv import dotenv_values
from scripts.audit_langfuse_cloud import execute
from scripts.export_phase10_scores import evaluate
from scripts.phase10_tracing import CaptureExporter, bounded_sdk_call

from food_recommender.infrastructure.observability import configure_logging
from food_recommender.infrastructure.telemetry.audit import audit_observations
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing, sdk_factory
from food_recommender.infrastructure.telemetry.ledger import TraceLedger
from food_recommender.infrastructure.telemetry.scores import (
    export_scores,
    score_payload,
)

ROOT = Path(__file__).resolve().parents[2]
FIELDS = "core,basic,io,metadata,usage,model,trace_context"


def private_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def fetch_recent(client, identities, start, end, *, max_pages=10):
    if (
        not identities
        or len(identities) > 64
        or len(set(identities)) != len(identities)
        or not all(re.fullmatch(r"[0-9a-f]{32}", identity) for identity in identities)
    ):
        raise ValueError("Read-back requires unique scoped synthetic trace IDs")
    filters = [
        {
            "type": "stringOptions",
            "column": "traceId",
            "operator": "any of",
            "value": identities,
        },
        {"type": "datetime", "column": "startTime", "operator": ">=", "value": start},
        {"type": "datetime", "column": "startTime", "operator": "<", "value": end},
    ]
    rows, seen, cursor = [], set(), None
    for _ in range(max_pages):
        params = {
            "filter": json.dumps(filters),
            "fromStartTime": start,
            "toStartTime": end,
            "fields": FIELDS,
            "limit": 100,
        }
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/public/v2/observations", params=params)
        response.raise_for_status()
        page = response.json()
        if any(row.get("traceId") not in identities for row in page["data"]):
            raise ValueError("Read-back returned an out-of-scope trace")
        rows.extend(page["data"])
        cursor = page.get("meta", {}).get("cursor")
        if not cursor:
            return rows
        if cursor in seen:
            raise ValueError("Repeated audit cursor")
        seen.add(cursor)
    raise ValueError("Read-back page budget exhausted")


def audit_scores(rows, expected):
    failures = []
    if len(rows) != len(expected) or len({row["id"] for row in rows}) != len(expected):
        failures.append("score_count_or_duplicate")
    for row in rows:
        want = expected.get(row["id"])
        if (
            not want
            or row.get("value") != want["value"]
            or row.get("name") != want["name"]
        ):
            failures.append("metric_value")
            continue
        subject = row.get("subject") or {}
        if (
            subject.get("id") != want["observation_id"]
            or subject.get("traceId") != want["trace_id"]
        ):
            failures.append("observation_association")
        if row.get("comment") or row.get("metadata") != want["metadata"]:
            failures.append("content_or_metadata")
    return {
        "stored_unique": len(rows),
        "expected_unique": len(expected),
        "failures": sorted(set(failures)),
        "passed": not failures,
    }


def audit_usage(rows):
    """Verify reported fixture usage; failed/cancelled attempts remain unknown."""
    generations = [row for row in rows if row.get("type") == "GENERATION"]
    successful = [
        row
        for row in generations
        if (row.get("metadata") or {}).get("outcome") == "success"
    ]
    passed = bool(successful) and all(
        row.get("model") == "gpt-4o-mini"
        and row.get("usageDetails") == {"input": 10, "output": 2, "total": 12}
        for row in successful
    )
    return {
        "generations": len(generations),
        "successful_with_expected_model_and_usage": len(successful) if passed else 0,
        "failed_or_cancelled_usage_not_inferred": len(generations) - len(successful),
        "passed": passed,
    }


def deliver_buffer(ledger, spans, delivery):
    """Deliver the bounded synthetic pilot after generation, in reviewed batches."""
    from opentelemetry.sdk.trace.export import SpanExportResult

    if len(spans) > 2048:
        raise ValueError("Synthetic capture exceeds the reviewed queue bound")
    for offset in range(0, len(spans), 32):
        result = ledger.filter_and_export(spans[offset : offset + 32], delivery.export)
        if result != SpanExportResult.SUCCESS:
            raise RuntimeError("Synthetic Cloud delivery failed")


class PacedClient(httpx.Client):
    """Keep reads below Hobby's 30 requests/minute without inducing quota errors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_request, self.calls = 0, 0

    def request(self, *args, **kwargs):
        pause = 2.2 - (time.monotonic() - self.last_request)
        if pause > 0:
            time.sleep(pause)
        self.last_request = time.monotonic()
        self.calls += 1
        return super().request(*args, **kwargs)


def deletion_rehearsal(client, tracing, immediate, path, run, conversation, start):
    asyncio.run(tracing.request_deletion(conversation))
    restarted = TraceLedger(path)
    delayed = [
        span for span in immediate.spans if f"{span.context.trace_id:032x}" == run.hex
    ]
    assert restarted.filter_and_export(delayed, len) == 0
    with restarted.connection() as db:
        session = db.execute(
            "SELECT session FROM traces WHERE id=?", (run.hex,)
        ).fetchone()[0]
    assert not restarted.register(session, uuid4().hex)
    response = client.request(
        "DELETE", "/api/public/traces", json={"traceIds": [run.hex]}
    )
    response.raise_for_status()
    deadline, polls = time.monotonic() + 180, 0
    while True:
        remaining = fetch_recent(
            client, [run.hex], start, datetime.now(UTC).isoformat()
        )
        polls += 1
        if not remaining or time.monotonic() >= deadline:
            break
        time.sleep(10)
    time.sleep(15)
    delayed_remaining = fetch_recent(
        client, [run.hex], start, datetime.now(UTC).isoformat()
    )
    passed = not remaining and not delayed_remaining
    if passed:
        restarted.confirm(run.hex)
    return {
        "submitted": 1,
        "polls": polls,
        "remaining": len(delayed_remaining),
        "late_export_suppressed_after_restart": True,
        "quiet_period_seconds": 15,
        "passed": passed,
    }


def demo(args):
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    args.private_dir = args.private_dir.resolve()
    if ROOT / ".local-tmp" not in args.private_dir.parents:
        raise ValueError("Private artifacts must stay under ignored .local-tmp")
    private_path = args.private_dir / "trace-links.json"
    if private_path.exists():
        raise ValueError("Use a new private directory for each demonstration")
    values = {
        k: v
        for k, v in dotenv_values(args.env_file).items()
        if k.startswith("LANGFUSE_")
    }
    values.update(
        LANGFUSE_ENABLED=True,
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
        LANGFUSE_CORRELATION_KEY=uuid4().hex,
        LANGFUSE_TRACING_ENVIRONMENT="phase11-synthetic",
        LANGFUSE_RELEASE="phase11-synthetic-v1",
        LANGFUSE_SAMPLE_RATE=1,
    )
    settings = TelemetrySettings(**values)
    public, secret = (
        settings.public_key.get_secret_value(),
        settings.secret_key.get_secret_value(),
    )
    headers = {
        "Authorization": "Basic "
        + base64.b64encode(f"{public}:{secret}".encode()).decode(),
        "x-langfuse-ingestion-version": "4",
    }
    destination = OTLPSpanExporter(
        endpoint=settings.base_url + "/api/public/otel/v1/traces",
        headers=headers,
        timeout=2,
        max_request_size=256 * 1024,
        session=requests.Session(),
    )
    delivery, immediate, buffered = (
        CaptureExporter(destination),
        CaptureExporter(),
        CaptureExporter(),
    )
    private_write(private_path, {"status": "started; no trace references yet"})
    ledger_path = args.private_dir / "traces.sqlite"
    ledger = TraceLedger(ledger_path)
    tracing = LazyTracing(
        settings,
        factory=lambda value: sdk_factory(value, buffered, ledger=ledger),
        ledger_path=ledger_path,
        revisions={
            "prompt_revision": "phase10-synthetic-v1",
            "dataset_revision": "phase10-v1",
        },
    )
    tracing.initialize()
    if tracing.client is None:
        raise RuntimeError("Synthetic SDK initialization unavailable")
    tracing.client._resources.tracer_provider.add_span_processor(
        SimpleSpanProcessor(immediate)
    )
    start = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    report = {
        "tasks": ["P11-11", "P11-12"],
        "verified_at": datetime.now(UTC).isoformat(),
        "mode": "real Cloud; real graph/OpenAI HTTP adapter with controlled provider/tools",
        "normal_conversation_export": False,
        "paid_provider_calls": 0,
        "fixture_content_uploaded": False,
    }
    try:
        scores, local_rows, runs = asyncio.run(
            evaluate(tracing, immediate, flush=False)
        )
        scenarios = asyncio.run(execute(tracing))
        runs.extend(scenarios)
        deletion_run, deletion_session = uuid4(), uuid4()
        with tracing.run(deletion_run, deletion_session):
            with tracing.observe("build-profile", "agent"):
                pass
        expected_scores = {
            score_payload(score)["score_id"]: score_payload(score) for score in scores
        }
        export_scores(tracing.client, scores)
        export_scores(tracing.client, scores)
        private = {
            "base_url": settings.base_url,
            "created_at": start,
            "trace_ids": runs,
            "score_ids": list(expected_scores),
            "deletion_trace_ids": [deletion_run.hex],
            "trace_links": [],
            "expires": "manual scoped purge; Hobby has no automatic retention",
        }
        private_write(private_path, private)
        if not bounded_sdk_call(tracing.client.flush, seconds=30):
            raise RuntimeError("Synthetic flush deadline")
        deliver_buffer(ledger, buffered.spans, delivery)
        with PacedClient(
            base_url=settings.base_url, auth=(public, secret), timeout=5
        ) as client:
            response = client.get("/api/public/projects")
            response.raise_for_status()
            projects = response.json()["data"]
            if len(projects) != 1:
                raise ValueError("Expected one dedicated project")
            private["trace_links"] = [
                f"{settings.base_url}/project/{projects[0]['id']}/traces/{identity}"
                for identity in runs
            ]
            private_write(private_path, private)
            deadline = time.monotonic() + 120
            all_runs = runs + [deletion_run.hex]
            while True:
                rows = fetch_recent(
                    client, all_runs, start, datetime.now(UTC).isoformat()
                )
                audits = [
                    audit_observations(
                        [row for row in rows if row["traceId"] == identity],
                        dict(
                            Counter(
                                span.name
                                for span in immediate.spans
                                if f"{span.context.trace_id:032x}" == identity
                            )
                        ),
                    )
                    for identity in all_runs
                ]
                if (
                    all(audit["passed"] for audit in audits)
                    or time.monotonic() >= deadline
                ):
                    break
                time.sleep(5)
            private_write(
                args.private_dir / "readback-private.json", {"observations": rows}
            )
            deadline = time.monotonic() + 90
            while True:
                response = client.get(
                    "/api/public/v3/scores",
                    params={
                        "id": ",".join(expected_scores),
                        "fields": "details,subject",
                        "limit": 100,
                    },
                )
                response.raise_for_status()
                score_audit = audit_scores(response.json()["data"], expected_scores)
                if score_audit["passed"] or time.monotonic() >= deadline:
                    break
                time.sleep(5)
            private_write(
                args.private_dir / "scores-private.json",
                {"scores": response.json()["data"]},
            )
            deletion = deletion_rehearsal(
                client,
                tracing,
                immediate,
                ledger_path,
                deletion_run,
                deletion_session,
                start,
            )
            report.update(
                project_access={
                    "status": 200,
                    "region": "US"
                    if settings.base_url.startswith("https://us.")
                    else "EU"
                    if settings.base_url == "https://cloud.langfuse.com"
                    else "JP",
                    "projects": 1,
                },
                traces=len(runs),
                scenario_turns=len(scenarios),
                fixture_turns=len(local_rows),
                observations=len(rows),
                audits=audits,
                usage_audit=audit_usage(rows),
                score_audit=score_audit,
                deletion=deletion,
                export={
                    "calls": delivery.calls,
                    "serialized_protobuf_bytes": delivery.bytes,
                    "observations_sent": len(delivery.spans),
                    "maximum_batch_observations": delivery.max_batch,
                    "maximum_batch_bytes": delivery.max_bytes,
                    "read_delete_calls": client.calls,
                    "wire_headers_and_compression_measured": False,
                    "synthetic_delivery": "bounded batches after fixture generation",
                },
                local_results=local_rows,
            )
        report["passed"] = (
            all(audit["passed"] for audit in audits)
            and score_audit["passed"]
            and report["usage_audit"]["passed"]
            and deletion["passed"]
        )
        report["versions"] = {
            name: version(name)
            for name in [
                "langfuse",
                "opentelemetry-api",
                "opentelemetry-sdk",
                "opentelemetry-exporter-otlp-proto-http",
                "httpx",
                "langgraph",
                "langchain-core",
            ]
        }
        report["limitations"] = [
            "Current organization usage and actual key issuance/revocation require owner console evidence.",
            "Retained synthetic demo traces require manual cleanup; Hobby has no automatic retention.",
            "Normal conversation export remains disabled; automatic purge scheduling, inaccessible old history, provider backups and unbounded late ingestion are not verified.",
        ]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        return report
    finally:
        bounded_sdk_call(tracing.client.shutdown, seconds=3)
        destination.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-cloud", action="store_true")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation/phase11/langfuse_demo_report.json",
    )
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    if not args.enable_cloud:
        parser.error("Synthetic Cloud export requires --enable-cloud")
    configure_logging()
    try:
        report = demo(args)
    except Exception as error:
        frames = traceback.extract_tb(error.__traceback__)
        print(
            json.dumps(
                {
                    "passed": False,
                    "failure_type": type(error).__name__,
                    "event_loop_stopped": str(error)
                    == "Event loop stopped before Future completed.",
                    "failure_code": next(
                        (
                            code
                            for code in (
                                "cannot reuse already awaited coroutine",
                                "cannot schedule new futures after shutdown",
                                "no running event loop",
                                "threads can only be started once",
                            )
                            if str(error) == code
                        ),
                        "other_runtime_failure",
                    ),
                    "failure_locations": [
                        {"function": frame.name, "line": frame.lineno}
                        for frame in frames[-4:]
                    ],
                    "details": "inspect private artifacts; credentials and response bodies omitted",
                }
            )
        )
        return 2
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "traces": report["traces"],
                "scores": report["score_audit"]["stored_unique"],
                "deletion": report["deletion"]["passed"],
            }
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
