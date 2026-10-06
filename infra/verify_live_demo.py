"""Prepare and remove an isolated catalog for the opt-in P11-04 live probe."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "pgvector/pgvector:pg16@sha256:a36250871de0833b8757561c72f2477ef1ddd1101afa4e617fb552e0de514c6b"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument(
        "--env-file",
        type=Path,
        required=True,
        help="Original owner-issued fresh provider configuration; never copied",
    )
    parser.add_argument("--minilm-root", type=Path, required=True)
    parser.add_argument("--clip-root", type=Path, required=True)
    parser.add_argument("--review-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.enable_live:
        parser.error("Paid provider calls require --enable-live")
    for path in (args.env_file, args.minilm_root, args.clip_root, args.review_cache):
        if not path.exists():
            parser.error("Required configuration/cache input missing")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"task": "P11-04", "passed": False, "turns": []}) + "\n"
    )
    scratch = ROOT / ".local-tmp"
    scratch.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="p11-04-", dir=scratch))
    name = work.name
    password = secrets.token_hex(32)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(
            ("OPENAI_", "TAVILY_", "LANGFUSE_", "DATABASE_", "POSTGRES_")
        )
    }
    env.update(
        POSTGRES_PASSWORD=password,
        FOODWISE_DB_PASSWORD=password,
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        LANGFUSE_ENABLED="false",
    )
    stages = []
    original = {}
    initial_inventory_complete = False

    def inventory():
        ids = subprocess.check_output(
            ["docker", "ps", "-q"], text=True, timeout=30
        ).split()
        if not ids:
            return {}
        records = json.loads(
            subprocess.check_output(["docker", "inspect", *ids], text=True, timeout=30)
        )
        return {
            r["Id"]: {
                "started_at": r["State"]["StartedAt"],
                "restarts": r["RestartCount"],
            }
            for r in records
        }

    def run(label, command, timeout=600):
        print("Running " + label, flush=True)
        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=ROOT / "backend",
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stages.append(
            {
                "stage": label,
                "returncode": result.returncode,
                "seconds": round(time.monotonic() - started, 3),
            }
        )
        # Setup has no provider keys. Live probe emits only allowlisted synthetic results.
        (work / (label + ".log")).write_text(
            (result.stdout + result.stderr).replace(password, "[redacted]")
        )
        if result.returncode:
            raise RuntimeError(label + " failed; inspect private redacted logs")
        return result.stdout.strip()

    try:
        original = inventory()
        initial_inventory_complete = True
        run(
            "start-database",
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--label",
                "foodwise.task=P11-04",
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "FOODWISE_DB_PASSWORD",
                "-e",
                "POSTGRES_DB=foodwise",
                "-p",
                "127.0.0.1::5432",
                "-v",
                f"{ROOT}/infra/postgres/01-bootstrap.sh:/docker-entrypoint-initdb.d/01-bootstrap.sh:ro",
                IMAGE,
            ],
        )
        port = run("database-port", ["docker", "port", name, "5432/tcp"]).rsplit(
            ":", 1
        )[1]
        env.update(
            DATABASE_URL=f"postgresql://foodwise:{password}@127.0.0.1:{port}/foodwise",
            MEDIA_ROOT=str(work / "media"),
            MINILM_ROOT=str(args.minilm_root.resolve()),
            CLIP_ROOT=str(args.clip_root.resolve()),
        )
        for _ in range(60):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    name,
                    "pg_isready",
                    "-U",
                    "postgres",
                    "-d",
                    "foodwise",
                ],
                check=False,
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Database startup timeout")
        run("migrations", [sys.executable, "-m", "alembic", "upgrade", "head"])
        run("checkpoints", [sys.executable, "scripts/setup_checkpoints.py"])
        shutil.copytree(args.review_cache, work / "downloads")
        seed = json.loads(
            run(
                "import",
                [
                    sys.executable,
                    "-m",
                    "food_recommender.cli.ingestion",
                    "import",
                    "--data-root",
                    str(ROOT / "data"),
                    "--recipe-zip",
                    str(ROOT / "data/synthetic-recipe-images.zip"),
                    "--report",
                    str(work / "manifest.json"),
                ],
            )
        )
        if seed["totals"] != {
            "imported": 329,
            "unchanged": 0,
            "rejected": 0,
            "unresolved": 16,
            "pending": 0,
        }:
            raise RuntimeError("Seed corpus mismatch")
        for module, flag, path, count in [
            ("text", "--model-root", args.minilm_root, 770),
            ("image", "--clip-root", args.clip_root, 118),
        ]:
            result = json.loads(
                run(
                    "index-" + module,
                    [
                        sys.executable,
                        "-m",
                        "food_recommender.cli." + module,
                        flag,
                        str(path.resolve()),
                        "index",
                    ],
                )
            )
            if result["embedded"] != count:
                raise RuntimeError("Vector corpus mismatch")
        run(
            "live-demonstration",
            [
                sys.executable,
                "scripts/phase11_live_demo.py",
                "--enable-live",
                "--env-file",
                str(args.env_file.resolve()),
                "--output",
                str(args.output.resolve()),
            ],
            timeout=430,
        )
    finally:
        subprocess.run(
            ["docker", "rm", "-f", "-v", name],
            check=False,
            capture_output=True,
            timeout=60,
        )
        try:
            remaining = inventory()
            preserved = initial_inventory_complete and all(
                remaining.get(k) == v for k, v in original.items()
            )
        except (OSError, subprocess.SubprocessError):
            preserved = False
        report = (
            json.loads(args.output.read_text())
            if args.output.exists()
            else {"task": "P11-04", "passed": False}
        )
        report["setup_stages"] = stages
        report["source_revision"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=30
        ).strip()
        report["script_hashes"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                ROOT / "infra/verify_live_demo.py",
                ROOT / "backend/scripts/phase11_live_demo.py",
            )
        }
        report["isolation"] = {
            "new_database_and_media": True,
            "provider_dotenv_copied": False,
            "owner_containers_unchanged": preserved,
            "disposable_container_removed": subprocess.run(
                ["docker", "inspect", name], check=False, capture_output=True
            ).returncode
            != 0,
        }
        if not all(
            v for k, v in report["isolation"].items() if k != "provider_dotenv_copied"
        ):
            report["passed"] = False
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        shutil.rmtree(work / "media", ignore_errors=True)
        shutil.rmtree(work / "downloads", ignore_errors=True)
        env.clear()
        print(
            json.dumps({"passed": report["passed"], "isolation": report["isolation"]}),
            flush=True,
        )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001 - never print provider/database diagnostics
        print("P11-04 verification failed; diagnostics redacted.", file=sys.stderr)
        raise SystemExit(2) from None
