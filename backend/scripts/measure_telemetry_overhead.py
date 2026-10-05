"""Fresh-process disabled/enabled SDK overhead against predeclared limits, offline only."""

import argparse
import asyncio
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from scripts.measure_phase10_performance import summarize
from scripts.phase10_acceptance import load_labels
from scripts.phase10_tracing import CaptureExporter, bounded_sdk_call, traced_case

from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing, sdk_factory

ROOT = Path(__file__).resolve().parents[2]


async def probe(enabled, repetitions):
    capture = CaptureExporter()
    settings = TelemetrySettings(
        LANGFUSE_ENABLED=enabled,
        LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",
        LANGFUSE_PUBLIC_KEY=uuid4().hex,
        LANGFUSE_SECRET_KEY="offline",
        LANGFUSE_CORRELATION_KEY="synthetic",
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
    )
    tracing = LazyTracing(settings, factory=lambda s: sdk_factory(s, capture))
    before = resource.getrusage(resource.RUSAGE_SELF)
    times = []
    case = load_labels()["cases"][0]
    for _ in range(repetitions + 1):
        started = time.perf_counter()
        await traced_case(case, tracing)
        times.append((time.perf_counter() - started) * 1000)
    if tracing.client:
        assert bounded_sdk_call(tracing.client.flush)
    after = resource.getrusage(resource.RUSAGE_SELF)
    batches = [getattr(capture, "max_batch", 0)]
    row = {
        "enabled": enabled,
        "first_turn_ms": times[0],
        "warm": summarize(times[1:]),
        "peak_rss_mib": after.ru_maxrss / 1024,
        "cpu_seconds": after.ru_utime
        + after.ru_stime
        - before.ru_utime
        - before.ru_stime,
        "export_calls": capture.calls,
        "serialized_bytes": capture.bytes,
        "observations": len(capture.spans),
        "max_batch_observations": max(batches),
        "max_batch_bytes": getattr(capture, "max_bytes", 0),
        "runs": len(times),
        "boundary": "graph/checkpoint/fake HTTP/fake MCP/OTLP encode; no remote latency",
    }
    await tracing.close()
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", choices=("disabled", "enabled"))
    parser.add_argument("--repetitions", type=int, default=100)
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(asyncio.run(probe(args.probe == "enabled", args.repetitions))))
        return
    limits = json.loads((ROOT / "evaluation/phase10/telemetry_limits.json").read_text())
    runs = []
    for mode in ("disabled", "enabled"):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.measure_telemetry_overhead",
                "--probe",
                mode,
                "--repetitions",
                str(args.repetitions),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **os.environ,
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
            },
        )
        assert result.returncode == 0, (
            "Local telemetry probe failed; inspect ignored diagnostics"
        )
        runs.append(json.loads(result.stdout))
    baseline, enabled = runs
    absolute = enabled["warm"]["p95_ms"] - baseline["warm"]["p95_ms"]
    relative = absolute / baseline["warm"]["p95_ms"]
    rss = enabled["peak_rss_mib"] - baseline["peak_rss_mib"]
    observations_per_run = enabled["observations"] / enabled["runs"]
    estimated_units_per_run = (
        observations_per_run + 1 + 3
    )  # trace + observations + three applicable pilot scores
    monthly = (
        estimated_units_per_run
        * limits["forecast_runs_per_day"]
        * limits["forecast_days"]
    )
    passed = (
        absolute <= limits["warm_p95_absolute_overhead_ms_max"]
        and relative <= limits["warm_p95_relative_overhead_max"]
        and rss <= limits["sdk_peak_rss_increase_mib_max"]
        and enabled["max_batch_bytes"] <= limits["export_request_bytes_max"]
    )
    report = {
        "date": "2026-10-05",
        "sdk": "4.16.0",
        "predeclared_limits": limits,
        "processes": runs,
        "overhead": {
            "warm_p95_ms": absolute,
            "warm_p95_fraction": relative,
            "peak_rss_mib": rss,
        },
        "volume_estimate": {
            "observations_per_run": observations_per_run,
            "units_per_run_with_three_scores": estimated_units_per_run,
            "monthly_units_at_100_runs_per_day": monthly,
            "units_source": "https://langfuse.com/docs/administration/billable-units",
            "recommended_sample_rate": 0.5 if monthly > 40000 else 1,
            "not_a_billing_or_project_quota_measurement": True,
        },
        "limits_passed": passed,
        "operational_readiness": False,
        "gaps": [
            "No enforced Hobby retention policy",
            "Forecast usage is hypothetical; existing project consumption unavailable",
            "Cold imports and SDK background managers have startup cost",
            "OS page cache and host load uncontrolled; 100 samples/mode on one machine",
            "Automatic durable remote purge scheduling and extended delayed-ingestion verification remain operational gates",
        ],
    }
    (ROOT / "evaluation/phase10/telemetry_overhead_report.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "overhead": report["overhead"],
                "limits_passed": passed,
                "monthly_units": monthly,
            }
        )
    )


if __name__ == "__main__":
    main()
