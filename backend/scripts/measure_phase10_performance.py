"""Offline graph timings and fresh-process pretrained CPU embedding resource probe."""

import argparse
import asyncio
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def summarize(values):
    values = sorted(values)
    return {
        "samples": len(values),
        "p50_ms": values[math.ceil(len(values) * 0.5) - 1],
        "p95_ms": values[math.ceil(len(values) * 0.95) - 1],
        "minimum_ms": values[0],
        "maximum_ms": values[-1],
    }


def embedding_probe(model, root):
    start = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_SELF)
    if model == "minilm":
        from food_recommender.infrastructure.embeddings.minilm import MiniLMEncoder

        encoder = MiniLMEncoder(root)

        def encode():
            return encoder.encode(("Italian pasta with tomatoes and basil",))
    else:
        from food_recommender.infrastructure.embeddings.clip import CLIPEncoder

        encoder = CLIPEncoder(root)

        def encode():
            return encoder.encode_texts(("Italian pasta with tomatoes and basil",))

    load_ms = (time.perf_counter() - start) * 1000
    timings = []
    for _ in range(11):
        start = time.perf_counter()
        encode()
        timings.append((time.perf_counter() - start) * 1000)
    after = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "model": model,
        "load_ms": load_ms,
        "first_encode_ms": timings[0],
        "warm_encode": summarize(timings[1:]),
        "peak_rss_mib": after.ru_maxrss / 1024,
        "cpu_seconds": after.ru_utime
        + after.ru_stime
        - before.ru_utime
        - before.ru_stime,
        "filesystem_cache": "uncontrolled; fresh process is not a cold OS page cache",
    }


async def measure(repetitions):
    from phase10_acceptance import execute_case, load_labels

    rows = []
    for repeat in range(repetitions):
        for case in load_labels()["cases"]:
            started = time.perf_counter()
            states, _, _ = await execute_case(case)
            rows.append(
                {
                    "case": case["id"],
                    "repeat": repeat,
                    "case_wall_ms": (time.perf_counter() - started) * 1000,
                    "turns": [state["metrics"] for state in states],
                }
            )
    turns = [turn for row in rows for turn in row["turns"]]
    return {
        "boundary": "real graph; fake OpenAI/MCP; in-memory checkpoints; excludes browser/DB/network",
        "cold_first_case_ms": rows[0]["case_wall_ms"],
        "end_to_end": summarize([turn["duration_ms"] for turn in turns]),
        "stages": {
            stage: summarize(
                [
                    s["duration_ms"]
                    for t in turns
                    for s in t["stages"]
                    if s["stage"] == stage
                ]
            )
            for stage in (
                "profile",
                "retrieval",
                "trend",
                "style",
                "nutrition",
                "recommendation",
            )
        },
        "usage": {
            "openai_attempts": sum(t["openai_calls"] for t in turns),
            "mcp_attempts": sum(t["tool_calls"] for t in turns),
            "search_calls": sum(t["search_calls"] for t in turns),
            "provider_tokens": None,
            "reason": "fixture inference reports no provider token usage; zero is not a measured live usage",
        },
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", choices=("minilm", "clip"))
    parser.add_argument("--model-root", type=Path)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evaluation/phase10/performance_report.json",
    )
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(embedding_probe(args.probe, args.model_root)))
        return
    report = {
        "machine": {
            "os": platform.platform(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "memory_mib": os.sysconf("SC_PHYS_PAGES")
            * os.sysconf("SC_PAGE_SIZE")
            / 1024**2,
            "cpu": next(
                (
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")
                ),
                "unknown",
            ),
            "threads": 1,
        },
        "graph": asyncio.run(measure(args.repetitions)),
        "embeddings": [],
    }
    for model in ("minilm", "clip"):
        result = subprocess.run(
            [
                sys.executable,
                __file__,
                "--probe",
                model,
                "--model-root",
                str(ROOT / ".local-tmp" / model),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            env={
                **os.environ,
                "OMP_NUM_THREADS": "1",
                "MKL_NUM_THREADS": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "HF_HUB_OFFLINE": "1",
            },
        )
        if result.returncode:
            raise RuntimeError(
                f"{model} measurement failed; inspect locally without exporting diagnostics"
            )
        report["embeddings"].append(json.loads(result.stdout))
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "end_to_end": report["graph"]["end_to_end"],
                "embeddings": report["embeddings"],
            }
        )
    )


if __name__ == "__main__":
    main()
