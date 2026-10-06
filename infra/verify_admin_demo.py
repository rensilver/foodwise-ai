"""P11-05: isolated offline administrator browser and transaction demonstration."""

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
PORTFOLIO_FILES = (
    "01-home.png",
    "02-text-citations.png",
    "03-hard-restriction.png",
    "04-image-mobile.png",
    "05-admin-preview.png",
    "06-admin-saved.png",
    "07-delete-confirmation.png",
)


def portfolio_assets(directory):
    """Accept only the complete known PNG set, without carrying private artifacts."""
    from PIL import Image, UnidentifiedImageError

    if {p.name for p in directory.iterdir()} != set(PORTFOLIO_FILES):
        raise ValueError("Incomplete or unexpected portfolio assets")
    assets = []
    for name in PORTFOLIO_FILES:
        path = directory / name
        if path.is_symlink():
            raise ValueError("Portfolio asset must be a regular file")
        try:
            with Image.open(path) as picture:
                if picture.format != "PNG" or picture.info:
                    raise ValueError("Expected metadata-free PNG")
                picture.load()
                width, height = picture.size
        except (OSError, UnidentifiedImageError) as error:
            raise ValueError("Invalid portfolio PNG") from error
        assets.append(
            {
                "file": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "width": width,
                "height": height,
            }
        )
    return assets


def inventory():
    ids = subprocess.check_output(["docker", "ps", "-q"], text=True, timeout=30).split()
    if not ids:
        return {}
    records = json.loads(
        subprocess.check_output(["docker", "inspect", *ids], text=True, timeout=30)
    )
    return {r["Id"]: (r["State"]["StartedAt"], r["RestartCount"]) for r in records}


def browser_cases(report):
    cases = []

    def collect(suite):
        for spec in suite.get("specs", []):
            for case in spec["tests"]:
                cases.append(
                    {
                        "title": spec["title"],
                        "passed": spec["ok"],
                        "status": case["status"],
                        "seconds": round(
                            sum(r["duration"] for r in case["results"]) / 1000, 3
                        ),
                    }
                )
        for child in suite.get("suites", []):
            collect(child)

    for suite in report["suites"]:
        collect(suite)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minilm-root", type=Path, required=True)
    parser.add_argument("--clip-root", type=Path, required=True)
    parser.add_argument("--pnpm", default="pnpm")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--portfolio-dir", type=Path, help="Capture the P11-06 portfolio journey"
    )
    args = parser.parse_args()
    task = "P11-06" if args.portfolio_dir else "P11-05"
    if args.portfolio_dir and args.portfolio_dir.exists():
        parser.error("Portfolio destination must be new; preserve prior captures")
    if os.path.sep in args.pnpm:
        args.pnpm = str(Path(args.pnpm).absolute())
    for path in (args.minilm_root, args.clip_root):
        if not path.is_dir():
            parser.error("Required offline model bundle missing")
    scratch = ROOT / ".local-tmp"
    scratch.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=task.lower() + "-", dir=scratch))
    name = work.name
    password = secrets.token_hex(32)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(
            (
                "OPENAI_",
                "TAVILY_",
                "LANGFUSE_",
                "OTEL_",
                "DATABASE_",
                "POSTGRES_",
                "TEST_DATABASE_",
            )
        )
    }
    env.update(
        POSTGRES_PASSWORD=password,
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        FOODWISE_BROWSER_ARTIFACTS=str(work / "browser"),
        P09_MINILM_ROOT=str(args.minilm_root.resolve()),
        P09_CLIP_ROOT=str(args.clip_root.resolve()),
        PLAYWRIGHT_BROWSERS_PATH=str(ROOT / ".local-tmp/playwright"),
        UV_CACHE_DIR=str(ROOT / ".local-tmp/uv-cache"),
        TMPDIR=str(work),
        PATH=str(Path(args.pnpm).absolute().parent) + os.pathsep + env.get("PATH", ""),
    )
    if args.portfolio_dir:
        env["FOODWISE_PORTFOLIO_DIR"] = str(work / "screenshots")
    report = {"task": task, "passed": False, "stages": [], "browser_cases": []}
    original = None
    failure = None

    def run(label, command, *, cwd=None, timeout=180):
        print("Running " + label, flush=True)
        started = time.monotonic()
        result = subprocess.run(
            command,
            cwd=cwd or ROOT / "backend",
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        report["stages"].append(
            {
                "stage": label,
                "returncode": result.returncode,
                "seconds": round(time.monotonic() - started, 3),
            }
        )
        log = work / (label + ".log")
        log.write_text((result.stdout + result.stderr).replace(password, "[redacted]"))
        log.chmod(0o600)
        if label == "administrator-browser-demo":
            report["browser_cases"] = browser_cases(json.loads(result.stdout))
        if result.returncode:
            raise RuntimeError(label + " failed")
        return result.stdout.strip()

    try:
        original = inventory()
        run(
            "start-database",
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--label",
                "foodwise.task=" + task,
                "--memory",
                "256m",
                "--memory-swap",
                "256m",
                "-e",
                "POSTGRES_PASSWORD",
                "-e",
                "POSTGRES_DB=foodwise_test",
                "-p",
                "127.0.0.1::5432",
                IMAGE,
                "-c",
                "shared_buffers=64MB",
                "-c",
                "max_connections=20",
            ],
        )
        port = run("database-port", ["docker", "port", name, "5432/tcp"]).rsplit(
            ":", 1
        )[1]
        env.update(
            TEST_DATABASE_ADMIN_URL=f"postgresql://postgres:{password}@127.0.0.1:{port}/foodwise_test",
            TEST_DATABASE_URL=f"postgresql://foodwise_test_app:synthetic-ci-application-password@127.0.0.1:{port}/foodwise_test",
        )
        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "postgres"],
                capture_output=True,
                timeout=10,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("Database startup timeout")
        run(
            "bootstrap-limited-role",
            [sys.executable, "scripts/bootstrap_test_database.py"],
        )
        # Next.js rejects backend-only settings, including disabled telemetry.
        env.pop("POSTGRES_PASSWORD")
        versions = run(
            "versions",
            [
                sys.executable,
                "-c",
                "import json,sys,importlib.metadata as m; print(json.dumps({'python':sys.version.split()[0], **{p:m.version(p) for p in ['fastapi','sqlalchemy','psycopg','sentence-transformers','transformers']}}))",
            ],
        )
        report["versions"] = json.loads(versions)
        run(
            "transaction-and-api-contracts",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/integration/test_admin_cancellation.py",
                "tests/integration/test_api_admin_catalog.py",
                "tests/integration/test_api_admin_auth.py",
                "tests/integration/test_repositories.py",
                "--junitxml=" + str(work / "contracts.xml"),
            ],
        )
        import xml.etree.ElementTree as ET

        suites = ET.parse(work / "contracts.xml").getroot()
        report["transaction_contracts"] = {
            key: sum(int(s.get(key, "0")) for s in suites.iter("testsuite"))
            for key in ("tests", "failures", "errors", "skipped")
        }
        if any(
            report["transaction_contracts"][k]
            for k in ("failures", "errors", "skipped")
        ):
            raise RuntimeError("Required database contracts did not all execute")
        run(
            "administrator-browser-demo",
            [
                args.pnpm,
                "exec",
                "playwright",
                "test",
                "--config",
                "playwright.integration.config.ts",
                "--grep",
                "P11-06 portfolio"
                if args.portfolio_dir
                else "administrator|restaurant administration",
                "--reporter=json",
            ],
            cwd=ROOT / "frontend",
            timeout=300,
        )
        expected_cases = 1 if args.portfolio_dir else 4
        if len(report["browser_cases"]) != expected_cases or not all(
            c["passed"] for c in report["browser_cases"]
        ):
            raise RuntimeError("Expected all required browser journeys")
        if args.portfolio_dir:
            report["screenshots"] = portfolio_assets(work / "screenshots")
            report["capture_scope"] = {
                "synthetic_inputs_only": True,
                "browser_chrome_captured": False,
                "password_fields_masked": True,
                "live_trends_available": False,
                "course_grading_equivalence_claimed": False,
            }
        receipt = run(
            "catalog-cleanup-receipt",
            [
                sys.executable,
                "-c",
                """
import json,os,psycopg
from food_recommender.retrieval.embedding_contracts import MINILM_MODEL,MINILM_REVISION,CLIP_MODEL,CLIP_REVISION
queries = {
 'restaurants': 'SELECT count(*) FROM restaurants',
 'recipes': 'SELECT count(*) FROM recipes',
 'admin_entities': "SELECT (SELECT count(*) FROM restaurants WHERE source_id='local-admin')+(SELECT count(*) FROM recipes WHERE source_id='local-admin')",
 'text_vectors': 'SELECT count(*) FROM text_embeddings',
 'image_vectors': 'SELECT count(*) FROM image_embeddings',
}
with psycopg.connect(os.environ['TEST_DATABASE_URL']) as c:
 counts={k:c.execute(q).fetchone()[0] for k,q in queries.items()}
 versions={'postgresql':c.execute('SHOW server_version').fetchone()[0], 'pgvector':c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()[0]}
print(json.dumps({'counts':counts,'versions':versions,'models':{'text':{'id':MINILM_MODEL,'revision':MINILM_REVISION},'image':{'id':CLIP_MODEL,'revision':CLIP_REVISION}}}))
""",
            ],
        )
        receipt = json.loads(receipt)
        report["catalog_after_demo"] = receipt["counts"]
        if receipt["counts"] != {
            "restaurants": 1,
            "recipes": 1,
            "admin_entities": 0,
            "text_vectors": 2,
            "image_vectors": 1,
        }:
            raise RuntimeError("Administrator records or vectors remain after deletion")
        report["models"] = receipt["models"]
        report["versions"].update(receipt["versions"])
        report["versions"].update(
            node=run("node-version", ["node", "--version"]),
            pnpm=run("pnpm-version", [args.pnpm, "--version"], cwd=ROOT / "frontend"),
            playwright=run(
                "playwright-version",
                [args.pnpm, "exec", "playwright", "--version"],
                cwd=ROOT / "frontend",
            ),
        )
        report["passed"] = True
    except Exception as error:  # noqa: BLE001 - record only the failure type
        failure = error
        report["failure_type"] = type(error).__name__
    finally:
        removed = subprocess.run(
            ["docker", "rm", "-f", "-v", name],
            capture_output=True,
            timeout=60,
            check=False,
        )
        try:
            remaining = inventory()
            preserved = original is not None and all(
                remaining.get(k) == v for k, v in original.items()
            )
        except (OSError, subprocess.SubprocessError):
            preserved = False
        report["source_revision"] = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=30
            ).strip()
            if (ROOT / ".git").exists()
            else "unavailable"
        )
        report["script_hashes"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                ROOT / "infra/verify_admin_demo.py",
                ROOT / "backend/scripts/serve_frontend_fixture.py",
                ROOT / "backend/tests/integration/test_admin_cancellation.py",
                ROOT / "backend/tests/integration/test_api_admin_catalog.py",
                ROOT / "backend/src/food_recommender/application/catalog/admin.py",
                ROOT / "frontend/playwright.integration.config.ts",
                ROOT / "frontend/tests/integration/admin-release.spec.ts",
                ROOT / "frontend/tests/integration/journeys.spec.ts",
                ROOT / "frontend/tests/integration/portfolio.spec.ts",
            )
            if p.exists()
        }
        if failure:
            diagnostics = scratch / "p11-admin-failure.log"
            diagnostics.write_text(
                "\n".join(p.read_text() for p in sorted(work.glob("*.log")))
            )
            diagnostics.chmod(0o600)
        if (
            report["passed"]
            and preserved
            and removed.returncode == 0
            and args.portfolio_dir
        ):
            try:
                shutil.copytree(work / "screenshots", args.portfolio_dir)
            except OSError as error:
                failure = error
                report["passed"] = False
                report["failure_type"] = type(error).__name__
        shutil.rmtree(work)
        env.clear()
        report["isolation"] = {
            "owner_containers_unchanged": preserved,
            "disposable_container_removed": removed.returncode == 0,
            "private_work_removed": not work.exists(),
            "owner_dotenv_read": False,
            "paid_provider_calls": False,
            "controlled_inference": True,
            "pretrained_cpu_embeddings": True,
        }
        report["passed"] = report["passed"] and preserved and removed.returncode == 0
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    if failure:
        raise RuntimeError(task + " failed; see sanitized report") from None
    print(json.dumps({"passed": report["passed"], "isolation": report["isolation"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001 - never print private diagnostics
        print("Browser demonstration failed; diagnostics redacted.", file=sys.stderr)
        raise SystemExit(2) from None
