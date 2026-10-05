"""P11-02: rehearse migrations, seed idempotency, health and durable restarts.

Creates and removes its own Compose project, credentials, images and volumes.
Uses recovered media and cached pinned models; never reads the owner's dotenv.
Run with the locked backend Python environment; see release-setup.md.
"""

import argparse
import hashlib
import io
import json
import os
import secrets
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from argon2 import PasswordHasher
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minilm-root", required=True, type=Path)
    parser.add_argument("--clip-root", required=True, type=Path)
    parser.add_argument("--review-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.minilm_root, args.clip_root, args.review_cache):
        if not path.is_dir():
            parser.error(f"Required cached input missing: {path}")
    archive = ROOT / "data/synthetic-recipe-images.zip"
    if not archive.is_file():
        parser.error("Restore the recovered recipe ZIP first")
    scratch = ROOT / ".local-tmp"
    scratch.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="p11-02-", dir=scratch))
    project = work.name.replace("_", "-")
    values = {
        "OPENAI_API_KEY": "synthetic-p11-02-no-inference",
        "TAVILY_API_KEY": "",
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "FOODWISE_DB_PASSWORD": secrets.token_hex(32),
        "ADMIN_PASSWORD_HASH": PasswordHasher().hash(secrets.token_urlsafe(32)),
        "MINILM_ROOT": str(args.minilm_root.resolve()),
        "CLIP_ROOT": str(args.clip_root.resolve()),
        "LANGFUSE_ENABLED": "false",
        "LANGFUSE_CONVERSATION_EXPORT_VERIFIED": "false",
    }
    dotenv = work / "rehearsal.env"
    dotenv.write_text("".join(f"{name}='{value}'\n" for name, value in values.items()))
    dotenv.chmod(0o600)
    override = work / "compose.yaml"
    override.write_text(f"""services:
  backend:
    image: {project}-backend:rehearsal
    mem_limit: 2304m
    memswap_limit: 2304m
    ports: !override ["127.0.0.1::8000"]
  mcp:
    image: {project}-backend:rehearsal
    mem_limit: 1536m
    memswap_limit: 1536m
  frontend:
    image: {project}-frontend:rehearsal
    ports: !override ["127.0.0.1::3000"]
""")
    # Do not let shell/provider settings override the private synthetic dotenv.
    env = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("LANGFUSE_", "OPENAI_", "TAVILY_", "COMPOSE_"))
        and name not in values
    }
    compose = [
        "docker",
        "compose",
        "--env-file",
        str(dotenv),
        "-p",
        project,
        "-f",
        str(ROOT / "compose.yaml"),
        "-f",
        str(ROOT / "compose.low-memory.yaml"),
        "-f",
        str(override),
    ]
    setup = compose + [
        "run",
        "--rm",
        "--no-deps",
        "--workdir",
        "/setup",
        "--volume",
        f"{ROOT}/backend:/setup:ro",
        "--volume",
        f"{ROOT}/data:/seed:ro",
        "--volume",
        f"{ROOT}/evaluation:/evidence:ro",
        "--volume",
        f"{args.review_cache.resolve()}:/review-cache:ro",
        "--volume",
        f"{args.clip_root.resolve()}:/var/lib/foodwise/models/clip:ro",
        "--env",
        "CLIP_ROOT=/var/lib/foodwise/models/clip",
        "backend",
    ]
    report = {
        "task": "P11-02",
        "date": datetime.now(UTC).date().isoformat(),
        "status": "running",
        "steps": [],
        "checks": {},
        "isolation": {
            "project": project,
            "provider_calls": 0,
            "owner_dotenv_read": False,
            "langfuse_enabled": False,
            "db_and_mcp_ports": "private",
        },
        "limitations": [
            "Cached pinned models and approved-host review downloads reused; new DB/media volumes",
            "Synthetic context/control-graph probe; live six-agent follow-ups remain P11-04",
            "Backup/restore remains P11-03; 16 source entity-review pairs preserved",
        ],
    }

    def run(label: str, command: list[str], timeout: int = 600) -> str:
        print(f"Running {label}", flush=True)
        start = time.monotonic()
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = result.stdout + result.stderr
        for name in (
            "POSTGRES_PASSWORD",
            "FOODWISE_DB_PASSWORD",
            "ADMIN_PASSWORD_HASH",
            "OPENAI_API_KEY",
        ):
            output = output.replace(values[name], "[redacted]")
        (work / f"{label}.log").write_text(output)
        report["steps"].append(
            {
                "label": label,
                "returncode": result.returncode,
                "seconds": round(time.monotonic() - start, 3),
            }
        )
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect private rehearsal logs")
        return result.stdout.strip()

    def probe(label: str, operation: str, *extra: str) -> dict:
        return json.loads(
            run(
                label,
                setup
                + ["python", "scripts/probe_phase11_persistence.py", operation, *extra],
            )
        )

    def address(service: str, port: str) -> str:
        return "http://" + run(f"address-{service}", compose + ["port", service, port])

    def health(
        client: httpx.Client, name: str, status: int, unavailable: tuple = ()
    ) -> None:
        response = client.get("/api/v1/health/ready")
        payload = response.json()
        assert response.status_code == status, (name, response.status_code)
        assert payload["status"] == ("ready" if status == 200 else "unavailable")
        for dependency in unavailable:
            assert payload["dependencies"][dependency] == "unavailable", name
        assert client.get("/api/v1/health/live").status_code == 200
        report["checks"][name] = {
            "http_status": status,
            "payload": payload,
            "liveness": 200,
        }

    def serving(label: str) -> None:
        run(
            label,
            compose + ["up", "-d", "--no-build", "--wait", "--wait-timeout", "180"],
        )

    def import_seed(label: str, imported: int, unchanged: int) -> None:
        result = json.loads(
            run(
                label,
                setup
                + [
                    "python",
                    "-m",
                    "food_recommender.cli.ingestion",
                    "import",
                    "--data-root",
                    "/seed",
                    "--mapping",
                    "/evidence/phase0/restaurant_reconciliation.json",
                    "--accepted",
                    "/evidence/phase3/accepted_restaurant_additions.json",
                    "--corrections",
                    "/evidence/phase3/restaurant_corrections.json",
                    "--recipe-zip",
                    "/seed/synthetic-recipe-images.zip",
                    "--report",
                    "/var/lib/foodwise/media/.setup/manifest.json",
                ],
            )
        )
        assert result["status"] == "completed"
        assert result["totals"] == {
            "imported": imported,
            "unchanged": unchanged,
            "rejected": 0,
            "unresolved": 16,
            "pending": 0,
        }
        report["checks"][label] = result

    def index(label: str, repeat: bool) -> None:
        for category, root, expected in (
            ("text", "minilm", 770),
            ("image", "clip", 118),
        ):
            flag = "--model-root" if category == "text" else "--clip-root"
            result = json.loads(
                run(
                    f"{label}-{category}",
                    setup
                    + [
                        "python",
                        "-m",
                        f"food_recommender.cli.{category}",
                        flag,
                        f"/var/lib/foodwise/models/{root}",
                        "index",
                    ],
                )
            )
            assert result["embedded"] == (0 if repeat else expected)
            assert result["unchanged"] == (expected if repeat else 0)
            report["checks"][f"{label}-{category}"] = result

    def owner_containers() -> dict:
        ids = subprocess.check_output(
            ["docker", "ps", "-q"], env=env, text=True
        ).split()
        if not ids:
            return {}
        records = json.loads(
            subprocess.check_output(["docker", "inspect", *ids], env=env, text=True)
        )
        return {
            r["Id"]: {
                "started_at": r["State"]["StartedAt"],
                "restarts": r["RestartCount"],
            }
            for r in records
        }

    original = {}
    try:
        original = owner_containers()
        report["script_hashes"] = {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__),
                ROOT / "backend/scripts/probe_phase11_persistence.py",
            )
        }
        report["source_revision"] = run("source-revision", ["git", "rev-parse", "HEAD"])
        report["docker_version"] = run(
            "docker-version", ["docker", "version", "--format", "{{.Server.Version}}"]
        )
        report["compose_version"] = run(
            "compose-version", ["docker", "compose", "version", "--short"]
        )
        run("compose-config", compose + ["config", "--quiet"])
        run("build-backend", compose + ["build", "backend"], 1500)
        run("build-frontend", compose + ["build", "frontend"], 1500)
        run(
            "database-start",
            compose + ["up", "-d", "db", "--wait", "--wait-timeout", "180"],
        )
        # Backend must serve liveness even when its required schema is absent.
        run(
            "uninitialized-services",
            compose + ["up", "-d", "--no-deps", "mcp", "backend"],
        )
        with httpx.Client(
            base_url=address("backend", "8000"), timeout=20, trust_env=False
        ) as client:
            for _ in range(60):
                try:
                    if client.get("/api/v1/health/live").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(1)
            health(client, "before-migrations", 503, ("schema",))
            run("migrate-fresh", setup + ["alembic", "upgrade", "head"])
            health(client, "before-checkpoints", 503, ("schema",))
            run("downgrade-empty", setup + ["alembic", "downgrade", "base"])
            health(client, "after-downgrade", 503, ("schema",))
            run("upgrade-again", setup + ["alembic", "upgrade", "head"])
            run("migration-parity", setup + ["alembic", "check"])
            run("checkpoint-setup", setup + ["python", "scripts/setup_checkpoints.py"])
            health(client, "empty-catalog-ready", 200)
            run(
                "copy-review-cache",
                setup
                + [
                    "python",
                    "-c",
                    "import shutil; shutil.copytree('/review-cache', '/var/lib/foodwise/media/.setup/downloads', dirs_exist_ok=True)",
                ],
            )
            import_seed("seed-first", 329, 0)
            index("index-first", False)
            before = probe("snapshot-before-repeat", "snapshot")
            assert before["migration"] == "0009_admin"
            for table, count in (
                ("restaurants", 210),
                ("recipes", 109),
                ("reviews", 10),
                ("media", 118),
                ("documents", 1006),
                ("text_embeddings", 770),
                ("image_embeddings", 118),
                ("ingestion_checkpoints", 329),
            ):
                assert before["tables"][f"public.{table}"]["rows"] == count
            import_seed("seed-repeat", 0, 329)
            index("index-repeat", True)
            after = probe("snapshot-after-repeat", "snapshot")
            assert before == after
            report["checks"]["repeat-preserves-every-row-and-media-hash"] = True
            run("migrate-noop", setup + ["alembic", "upgrade", "head"])
            run(
                "checkpoint-setup-repeat",
                setup + ["python", "scripts/setup_checkpoints.py"],
            )
            assert probe("snapshot-after-setup-repeat", "snapshot") == before
            report["checks"]["setup-repeat-preserves-every-row"] = True
            serving("full-stack-start")
            client.base_url = address("backend", "8000")
            conversation = client.post("/api/v1/conversations")
            assert conversation.status_code == 201
            conversation_id = conversation.json()["id"]
            report["checks"]["context-seed"] = probe(
                "context-seed", "seed-context", "--conversation", conversation_id
            )
            image = io.BytesIO()
            Image.new("RGB", (8, 8), "green").save(image, format="PNG")
            upload = client.post(
                "/api/v1/media",
                files={"file": ("probe.png", image.getvalue(), "image/png")},
            )
            assert upload.status_code == 201
            media_id = upload.json()["id"]
            original_image = client.get(f"/api/v1/media/{media_id}")
            assert original_image.status_code == 200
            history = client.get(f"/api/v1/conversations/{conversation_id}").json()
            assert len(history["messages"]) == 1
            baseline = probe("snapshot-before-restart", "snapshot")
            report["baseline"] = baseline
            report["checks"]["missing-path-readiness"] = probe(
                "readiness-variants", "readiness"
            )
            run("mcp-stop", compose + ["stop", "mcp"])
            health(client, "mcp-outage", 503, ("mcp",))
            serving("recover-mcp")
            client.base_url = address("backend", "8000")
            health(client, "mcp-recovered", 200)
            run("database-stop", compose + ["stop", "db"])
            health(client, "database-outage", 503, ("database", "schema", "mcp"))
            serving("recover-database")
            client.base_url = address("backend", "8000")
            health(client, "database-recovered", 200)
            run("restart-services", compose + ["restart"])
            serving("wait-after-restart")
            client.base_url = address("backend", "8000")
            health(client, "after-restart", 200)
            assert probe("snapshot-after-restart", "snapshot") == baseline
            report["checks"]["restart-preserves-every-row-and-media-hash"] = True
            assert (
                client.get(f"/api/v1/conversations/{conversation_id}").json() == history
            )
            assert (
                client.get(f"/api/v1/media/{media_id}").content
                == original_image.content
            )
            cookies = dict(client.cookies)
        run("down-preserve-volumes", compose + ["down"])
        serving("recreate-services")
        with httpx.Client(
            base_url=address("backend", "8000"),
            cookies=cookies,
            timeout=20,
            trust_env=False,
        ) as client:
            health(client, "after-recreation", 200)
            assert probe("snapshot-after-recreation", "snapshot") == baseline
            report["checks"]["recreation-preserves-every-row-and-media-hash"] = True
            assert (
                client.get(f"/api/v1/conversations/{conversation_id}").json() == history
            )
            assert (
                client.get(f"/api/v1/media/{media_id}").content
                == original_image.content
            )
            with httpx.Client(
                base_url=str(client.base_url), trust_env=False
            ) as stranger:
                assert (
                    stranger.get(f"/api/v1/conversations/{conversation_id}").status_code
                    == 404
                )
                assert stranger.get(f"/api/v1/media/{media_id}").status_code == 404
            report["checks"]["owned-history-upload-and-stranger-denial"] = True
            report["checks"]["context-after-recreation"] = probe(
                "context-after-recreation",
                "advance-context",
                "--conversation",
                conversation_id,
            )
        with httpx.Client(
            base_url=address("frontend", "3000"), timeout=20, trust_env=False
        ) as frontend:
            assert frontend.get("/health/live").status_code == 200
            for category, total in (("restaurants", 210), ("recipes", 109)):
                result = frontend.get(f"/api/v1/{category}?limit=1")
                assert result.status_code == 200 and result.json()["total"] == total
        report["checks"]["frontend-proxy-after-recreation"] = True
        report["status"] = "passed"
    except BaseException as error:
        report["status"] = "failed"
        report["failure_type"] = type(error).__name__
        raise
    finally:
        previously_failed = report["status"] != "passed"
        cleanup_error = None
        try:
            run("cleanup-project", compose + ["down", "--volumes", "--remove-orphans"])
            run(
                "cleanup-images",
                [
                    "docker",
                    "image",
                    "rm",
                    f"{project}-backend:rehearsal",
                    f"{project}-frontend:rehearsal",
                ],
            )
            current = owner_containers()
            assert all(
                current.get(identity) == state for identity, state in original.items()
            )
            report["cleanup"] = {
                "project_removed": True,
                "owner_containers_unchanged": True,
            }
        except (
            OSError,
            RuntimeError,
            subprocess.SubprocessError,
            AssertionError,
            ValueError,
        ) as error:
            cleanup_error = error
            report["status"] = "failed"
            report["cleanup"] = {"failure_type": type(error).__name__}
        finally:
            dotenv.unlink(missing_ok=True)
            report.setdefault("cleanup", {})["temporary_credentials_removed"] = True
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
        if cleanup_error is not None and not previously_failed:
            raise RuntimeError(
                "Rehearsal cleanup failed; inspect private logs"
            ) from cleanup_error
    print(f"P11-02 {report['status']}: {args.output}")


if __name__ == "__main__":
    main()
