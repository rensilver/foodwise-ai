"""Opt-in synthetic execute/export/fetch/audit. No paid inference or fixture content export."""

import argparse
import asyncio
import base64
import json
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import requests
from dotenv import dotenv_values
from scripts.phase10_acceptance import load_labels
from scripts.phase10_tracing import CaptureExporter, traced_case

from food_recommender.infrastructure.observability import configure_logging
from food_recommender.infrastructure.telemetry.audit import (
    audit_observations,
    fetch_observations,
)
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing, sdk_factory

ROOT = Path(__file__).resolve().parents[2]


async def execute(tracing):
    cases = load_labels()["cases"]
    followup = next(c for c in cases if len(c["turns"]) > 1)
    clarification = next(
        c for c in cases if c["turns"][0]["expected"] == "clarification"
    )
    runs = []
    for case, options in [
        (cases[0], {}),
        (followup, {}),
        (clarification, {}),
        (cases[0], {"retry": True}),
        (cases[0], {"malformed": True}),
        (cases[0], {"cancel": True}),
    ]:
        _, refs = await traced_case(case, tracing, **options)
        runs.extend(refs)
    return runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-cloud", action="store_true")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation/phase10/langfuse_cloud_audit.json",
    )
    args = parser.parse_args()
    if not args.enable_cloud:
        parser.error("Cloud export requires --enable-cloud")
    configure_logging()
    values = {
        k: v
        for k, v in dotenv_values(args.env_file).items()
        if k.startswith("LANGFUSE_")
    }
    values.update(
        LANGFUSE_ENABLED=True,
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
        LANGFUSE_CORRELATION_KEY=uuid4().hex,
    )
    settings = TelemetrySettings(**values)
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    assert settings.public_key and settings.secret_key
    public, secret = (
        settings.public_key.get_secret_value(),
        settings.secret_key.get_secret_value(),
    )
    destination = OTLPSpanExporter(
        endpoint=settings.base_url + "/api/public/otel/v1/traces",
        headers={
            "Authorization": "Basic "
            + base64.b64encode(f"{public}:{secret}".encode()).decode(),
            "x-langfuse-ingestion-version": "4",
        },
        timeout=2,
        max_request_size=256 * 1024,
        session=requests.Session(),
    )
    capture = CaptureExporter(destination)
    tracing = LazyTracing(
        settings,
        factory=lambda settings: sdk_factory(settings, capture),
        revisions={
            "prompt_revision": "phase10-synthetic-v1",
            "dataset_revision": "phase10-v1",
        },
    )
    start = datetime.now(UTC) - timedelta(minutes=1)
    runs = asyncio.run(execute(tracing))
    tracing.client.flush()
    private_path = ROOT / ".local-tmp/langfuse-audit-private.json"
    previous = (
        json.loads(private_path.read_text()).get("trace_ids", [])
        if private_path.exists()
        else []
    )
    private_path.write_text(
        json.dumps(
            {
                "trace_ids": previous + runs,
                "region": "US",
                "timestamp": start.isoformat(),
            },
            indent=2,
        )
        + "\n"
    )
    audits = []
    with httpx.Client(
        base_url=settings.base_url, auth=(public, secret), timeout=5
    ) as client:
        for trace_id in runs:
            expected = dict(
                Counter(
                    s.name
                    for s in capture.spans
                    if f"{s.context.trace_id:032x}" == trace_id
                )
            )
            deadline = time.monotonic() + 60
            while True:
                rows = fetch_observations(
                    client,
                    trace_id,
                    start.isoformat(),
                    datetime.now(UTC).isoformat(),
                )
                audit = audit_observations(rows, expected)
                if audit["passed"] or time.monotonic() >= deadline:
                    break
                time.sleep(5)
            audits.append(audit)
            # Project Hobby read API quota is 30 requests/minute.
            time.sleep(2.1)
    report = {
        "date": "2026-10-05",
        "sdk": "4.16.0",
        "region": "US",
        "mode": "synthetic graph and mocked OpenAI HTTP, metadata only",
        "traces": len(runs),
        "export_calls": capture.calls,
        "serialized_bytes": capture.bytes,
        "audits": audits,
        "passed": all(a["passed"] for a in audits),
        "normal_conversation_export": False,
        "paid_provider_calls": 0,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    tracing.client.shutdown()
    print(json.dumps({"passed": report["passed"], "traces": len(runs)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
