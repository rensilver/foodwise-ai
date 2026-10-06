"""P11-03 isolated PostgreSQL + media recovery rehearsal, with no owner dotenv.

Uses fresh source/target Compose projects and separate credentials/volumes.
Only its own projects are removed; existing containers and configuration stay
untouched. Raw backup bytes are private, ignored and removed after verification.
"""

import argparse
import hashlib
import io
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from argon2 import PasswordHasher
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def file_identity(path: Path) -> dict:
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest}


def verify_pair(directory: Path, manifest: dict) -> None:
    for name in ("database.dump", "media.tar"):
        path = directory / name
        if (
            path.is_symlink()
            or not path.is_file()
            or file_identity(path) != manifest[name]
        ):
            raise ValueError(
                "Backup pair missing or corrupted; restore was not started"
            )


class Rehearsal:
    def __init__(self, args: argparse.Namespace, report: dict):
        self.args = args
        self.report = report
        scratch = ROOT / ".local-tmp"
        scratch.mkdir(exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="p11-03-", dir=scratch))
        self.projects = [self.work.name + "-source", self.work.name + "-target"]
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("LANGFUSE_", "OPENAI_", "TAVILY_", "COMPOSE_"))
            and k
            not in (
                "POSTGRES_PASSWORD",
                "FOODWISE_DB_PASSWORD",
                "ADMIN_PASSWORD_HASH",
                "MINILM_ROOT",
                "CLIP_ROOT",
            )
        }
        self.values = []
        self.dotenvs = []
        self.commands = []
        for project in self.projects:
            values = {
                "OPENAI_API_KEY": "synthetic-p11-03-no-inference",
                "TAVILY_API_KEY": "",
                "POSTGRES_PASSWORD": secrets.token_hex(32),
                "FOODWISE_DB_PASSWORD": secrets.token_hex(32),
                "ADMIN_PASSWORD_HASH": PasswordHasher().hash(secrets.token_urlsafe(32)),
                "MINILM_ROOT": str(args.minilm_root.resolve()),
                "CLIP_ROOT": str(args.clip_root.resolve()),
                "LANGFUSE_ENABLED": "false",
                "LANGFUSE_CONVERSATION_EXPORT_VERIFIED": "false",
            }
            self.values.extend(v for v in values.values() if v)
            dotenv = self.work / f"{project}.env"
            dotenv.write_text("".join(f"{k}='{v}'\n" for k, v in values.items()))
            dotenv.chmod(0o600)
            self.dotenvs.append(dotenv)
            override = self.work / f"{project}.yaml"
            override.write_text(f"""services:
  backend:
    image: {self.work.name}-backend:rehearsal
    mem_limit: 2304m
    memswap_limit: 2304m
    ports: !override ["127.0.0.1::8000"]
  mcp:
    image: {self.work.name}-backend:rehearsal
    mem_limit: 1536m
    memswap_limit: 1536m
  frontend:
    image: {self.work.name}-frontend:rehearsal
    ports: !override ["127.0.0.1::3000"]
""")
            self.commands.append(
                [
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
            )

    def run(
        self,
        label: str,
        command: list[str],
        *,
        input_file: Path | None = None,
        output_file: Path | None = None,
        timeout: int = 600,
    ) -> str:
        print(f"Running {label}", flush=True)
        started = time.monotonic()
        # Binary archives must never pass through text decoding or logs.
        incoming = input_file.open("rb") if input_file else None
        outgoing = output_file.open("xb") if output_file else None
        if output_file:
            output_file.chmod(0o600)
        try:
            # Snap Docker requires pipes at its process boundary. Pump archive
            # bytes concurrently, without retaining an entire volume in RAM.
            with (
                subprocess.Popen(
                    command,
                    cwd=ROOT,
                    env=self.env,
                    stdin=subprocess.PIPE if incoming else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ) as process,
                ThreadPoolExecutor(max_workers=3) as pool,
            ):
                assert process.stdout is not None and process.stderr is not None
                output = (
                    pool.submit(shutil.copyfileobj, process.stdout, outgoing)
                    if outgoing
                    else pool.submit(process.stdout.read)
                )
                errors = pool.submit(process.stderr.read)

                def send_input() -> None:
                    assert incoming is not None and process.stdin is not None
                    try:
                        with process.stdin:
                            shutil.copyfileobj(incoming, process.stdin)
                    except BrokenPipeError:
                        pass  # Preserve the subprocess's real failure below.

                pending_input = pool.submit(send_input) if incoming else None
                try:
                    returncode = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise
                if pending_input:
                    pending_input.result()
                stdout_bytes = output.result()
                result = subprocess.CompletedProcess(
                    command, returncode, stdout_bytes, errors.result()
                )
        finally:
            if incoming:
                incoming.close()
            if outgoing:
                outgoing.close()
        stdout = result.stdout.decode() if result.stdout else ""
        log = stdout + result.stderr.decode(errors="replace")
        for value in self.values:
            log = log.replace(value, "[redacted]")
        (self.work / f"{label}.log").write_text(log)
        self.report["steps"].append(
            {
                "label": label,
                "returncode": result.returncode,
                "seconds": round(time.monotonic() - started, 3),
            }
        )
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect private rehearsal logs")
        return stdout.strip()

    def compose(self, target: int, *command: str) -> list[str]:
        return self.commands[target] + list(command)

    def setup(self, target: int, *command: str) -> list[str]:
        return self.compose(
            target,
            "run",
            "--rm",
            "--no-deps",
            "-T",
            "--workdir",
            "/setup",
            "--volume",
            f"{ROOT}/backend:/setup:ro",
            "--volume",
            f"{ROOT}/data:/seed:ro",
            "--volume",
            f"{ROOT}/evaluation:/evidence:ro",
            "--volume",
            f"{self.args.review_cache.resolve()}:/review-cache:ro",
            "--volume",
            f"{self.args.clip_root.resolve()}:/var/lib/foodwise/models/clip:ro",
            "--env",
            "CLIP_ROOT=/var/lib/foodwise/models/clip",
            "backend",
            *command,
        )

    def probe(
        self,
        target: int,
        label: str,
        operation: str,
        *extra: str,
        script: str = "probe_phase11_restore",
    ) -> dict:
        return json.loads(
            self.run(
                label,
                self.setup(
                    target, "python", "-m", f"scripts.{script}", operation, *extra
                ),
            )
        )

    def address(self, target: int, service: str, port: str) -> str:
        return "http://" + self.run(
            f"address-{target}-{service}", self.compose(target, "port", service, port)
        )

    def start(self, target: int) -> None:
        self.run(
            f"stack-start-{target}",
            self.compose(
                target, "up", "-d", "--no-build", "--wait", "--wait-timeout", "180"
            ),
        )

    def inventory(self) -> dict:
        ids = self.run("container-inventory", ["docker", "ps", "-q"]).split()
        if not ids:
            return {}
        # Never log inspect output: it includes other applications' environment.
        result = subprocess.run(
            ["docker", "inspect", *ids], env=self.env, capture_output=True, check=True
        )
        return {
            r["Id"]: {
                "started_at": r["State"]["StartedAt"],
                "restarts": r["RestartCount"],
            }
            for r in json.loads(result.stdout)
        }

    def cleanup(self, original: dict) -> None:
        errors = []
        try:
            for target in (0, 1):
                try:
                    self.run(
                        f"cleanup-project-{target}",
                        self.compose(target, "down", "--volumes", "--remove-orphans"),
                    )
                except Exception as error:
                    errors.append(type(error).__name__)
            try:
                self.run(
                    "cleanup-images",
                    [
                        "docker",
                        "image",
                        "rm",
                        f"{self.work.name}-backend:rehearsal",
                        f"{self.work.name}-frontend:rehearsal",
                    ],
                )
                current = self.inventory()
                assert all(current.get(k) == v for k, v in original.items())
            except Exception as error:
                errors.append(type(error).__name__)
            self.report["cleanup"] = {
                "projects_removed": not errors,
                "owner_containers_unchanged": not errors,
            }
        finally:
            for dotenv in self.dotenvs:
                dotenv.unlink(missing_ok=True)
            for name in ("database.dump", "media.tar", "backup-manifest.json"):
                (self.work / name).unlink(missing_ok=True)
            self.report.setdefault("cleanup", {}).update(
                {"temporary_credentials_removed": True, "raw_backups_removed": True}
            )
        if errors:
            raise RuntimeError("Rehearsal cleanup failed")


def catalog_images(client: httpx.Client) -> dict:
    """Read every catalog image through its actual entity route and compare bytes."""
    images = []
    for category, total in (("restaurants", 210), ("recipes", 109)):
        for offset in range(0, total, 100):
            response = client.get(
                f"/api/v1/{category}", params={"limit": 100, "offset": offset}
            )
            assert response.status_code == 200 and response.json()["total"] == total
            for item in response.json()["items"]:
                assert item["citations"]
                for media in item["images"]:
                    entity_id = item["data"]["id"]
                    response = client.get(
                        f"/api/v1/{category}/{entity_id}/images/{media['id']}"
                    )
                    assert response.status_code == 200
                    with Image.open(io.BytesIO(response.content)) as decoded:
                        decoded.verify()
                    images.append(
                        (
                            category,
                            entity_id,
                            media["id"],
                            hashlib.sha256(response.content).hexdigest(),
                        )
                    )
    # Review media is scoped retrieval evidence, separate from browse thumbnails.
    assert len(images) == 109
    return {
        "served_images": len(images),
        "sha256": hashlib.sha256(json.dumps(sorted(images)).encode()).hexdigest(),
        "citations_present": True,
        "decoding_valid": True,
    }


def exercise(rehearsal: Rehearsal, report: dict) -> None:
    r = rehearsal
    checks = report["checks"]
    report["source_revision"] = r.run("source-revision", ["git", "rev-parse", "HEAD"])
    report["script_hashes"] = {
        str(p.relative_to(ROOT)): file_identity(p)["sha256"]
        for p in (
            Path(__file__),
            ROOT / "backend/scripts/backup_media.py",
            ROOT / "backend/scripts/probe_phase11_restore.py",
            ROOT / "backend/scripts/probe_phase11_persistence.py",
        )
    }
    report["docker_version"] = r.run(
        "docker-version", ["docker", "version", "--format", "{{.Server.Version}}"]
    )
    report["compose_version"] = r.run(
        "compose-version", ["docker", "compose", "version", "--short"]
    )
    for target in (0, 1):
        r.run(f"compose-config-{target}", r.compose(target, "config", "--quiet"))
    for service in ("backend", "frontend"):
        r.run(f"build-{service}", r.compose(0, "build", service), timeout=1500)
    r.run(
        "source-db-start",
        r.compose(0, "up", "-d", "db", "--wait", "--wait-timeout", "180"),
    )
    r.run("source-migrations", r.setup(0, "alembic", "upgrade", "head"))
    r.run("source-checkpoints", r.setup(0, "python", "scripts/setup_checkpoints.py"))
    r.run(
        "source-review-cache",
        r.setup(
            0,
            "python",
            "-c",
            "import shutil; shutil.copytree('/review-cache', '/var/lib/foodwise/media/.setup/downloads', dirs_exist_ok=True)",
        ),
    )
    imported = json.loads(
        r.run(
            "source-import",
            r.setup(
                0,
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
            ),
        )
    )
    assert imported["status"] == "completed" and imported["totals"] == {
        "imported": 329,
        "unchanged": 0,
        "rejected": 0,
        "unresolved": 16,
        "pending": 0,
    }
    checks["source-import"] = imported
    for category, flag, root, count in (
        ("text", "--model-root", "minilm", 770),
        ("image", "--clip-root", "clip", 118),
    ):
        indexed = json.loads(
            r.run(
                f"source-index-{category}",
                r.setup(
                    0,
                    "python",
                    "-m",
                    f"food_recommender.cli.{category}",
                    flag,
                    f"/var/lib/foodwise/models/{root}",
                    "index",
                ),
            )
        )
        assert indexed["embedded"] == count
        checks[f"source-index-{category}"] = indexed
    r.start(0)
    with httpx.Client(
        base_url=r.address(0, "backend", "8000"), timeout=30, trust_env=False
    ) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        response = client.post("/api/v1/conversations")
        assert response.status_code == 201
        conversation = response.json()["id"]
        checks["context-seed"] = r.probe(
            0,
            "context-seed",
            "seed-context",
            "--conversation",
            conversation,
            script="probe_phase11_persistence",
        )
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), "green").save(buffer, format="PNG")
        response = client.post(
            "/api/v1/media",
            files={"file": ("probe.png", buffer.getvalue(), "image/png")},
        )
        assert response.status_code == 201
        media_id = response.json()["id"]
        r.probe(
            0,
            "link-upload",
            "link-upload",
            "--conversation",
            conversation,
            "--media-id",
            media_id,
        )
        image = client.get(f"/api/v1/media/{media_id}")
        assert image.status_code == 200
        history = client.get(f"/api/v1/conversations/{conversation}").json()
        cookies = dict(client.cookies)
        checks["catalog-images-before-backup"] = catalog_images(client)
    # No running API/MCP/frontend or worker is permitted during this paired backup.
    r.run("quiesce-source-writers", r.compose(0, "stop", "frontend", "backend", "mcp"))
    baseline = r.probe(
        0, "source-snapshot", "snapshot", script="probe_phase11_persistence"
    )
    assert baseline["media"]["files"] == 119
    checks["integrity-before"] = r.probe(0, "source-integrity", "integrity")
    checks["retrieval-before"] = r.probe(0, "source-retrieval", "retrieval")
    volume = json.loads(
        r.run(
            "source-volume-snapshot",
            r.setup(0, "python", "scripts/backup_media.py", "snapshot"),
        )
    )
    report["baseline"] = baseline
    report["media_volume"] = volume
    database = r.work / "database.dump"
    media = r.work / "media.tar"
    r.run(
        "backup-database",
        r.compose(
            0,
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "postgres",
            "-d",
            "foodwise",
            "--format=custom",
        ),
        output_file=database,
    )
    r.run(
        "backup-media",
        r.setup(0, "python", "scripts/backup_media.py", "create"),
        output_file=media,
    )
    manifest = {
        name: file_identity(r.work / name) for name in ("database.dump", "media.tar")
    }
    manifest_path = r.work / "backup-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest_path.chmod(0o600)
    verify_pair(r.work, manifest)
    report["backup_pair"] = manifest
    # Corrupt one byte: pair validation must reject it before any target mutation.
    with media.open("r+b") as handle:
        first = handle.read(1)
        handle.seek(0)
        handle.write(bytes([first[0] ^ 1]))
    try:
        try:
            verify_pair(r.work, manifest)
        except ValueError:
            checks["corrupt-backup-rejected-before-restore"] = True
        else:
            raise AssertionError("Corrupt archive accepted")
    finally:
        with media.open("r+b") as handle:
            handle.write(first)
    verify_pair(r.work, manifest)
    # Remove the source before recovery, proving retained volumes cannot help.
    r.run(
        "remove-source-volumes", r.compose(0, "down", "--volumes", "--remove-orphans")
    )
    r.run(
        "fresh-target-db",
        r.compose(1, "up", "-d", "db", "--wait", "--wait-timeout", "180"),
    )
    empty = r.run(
        "target-is-empty",
        r.compose(
            1,
            "exec",
            "-T",
            "db",
            "psql",
            "-U",
            "postgres",
            "-d",
            "foodwise",
            "-tAc",
            "SELECT count(*) FROM pg_tables WHERE schemaname IN ('public','foodwise_checkpoints')",
        ),
    )
    assert empty == "0"
    checks["target-fresh-with-new-credentials"] = True
    verify_pair(r.work, manifest)
    r.run(
        "restore-database",
        r.compose(
            1,
            "exec",
            "-T",
            "db",
            "pg_restore",
            "-U",
            "postgres",
            "-d",
            "foodwise",
            "--clean",
            "--if-exists",
            "--single-transaction",
            "--exit-on-error",
        ),
        input_file=database,
    )
    restored_volume = json.loads(
        r.run(
            "restore-media",
            r.setup(1, "python", "scripts/backup_media.py", "restore"),
            input_file=media,
        )
    )
    assert restored_volume == volume
    restored = r.probe(
        1, "target-snapshot", "snapshot", script="probe_phase11_persistence"
    )
    assert restored == baseline
    checks["every-row-vector-checkpoint-and-media-hash-identical"] = True
    checks["entire-media-volume-identical"] = True
    assert r.probe(1, "target-integrity", "integrity") == checks["integrity-before"]
    assert r.probe(1, "target-retrieval", "retrieval") == checks["retrieval-before"]
    checks["constraints-owners-links-and-search-results-identical"] = True
    r.run("target-migration-parity", r.setup(1, "alembic", "check"))
    r.start(1)
    with httpx.Client(
        base_url=r.address(1, "backend", "8000"),
        cookies=cookies,
        timeout=30,
        trust_env=False,
    ) as client:
        readiness = client.get("/api/v1/health/ready")
        assert readiness.status_code == 200
        checks["restored-readiness"] = readiness.json()
        assert client.get(f"/api/v1/conversations/{conversation}").json() == history
        assert client.get(f"/api/v1/media/{media_id}").content == image.content
        assert catalog_images(client) == checks["catalog-images-before-backup"]
        checks["all-catalog-image-routes-preserved"] = True
        with httpx.Client(base_url=str(client.base_url), trust_env=False) as stranger:
            assert (
                stranger.get(f"/api/v1/conversations/{conversation}").status_code == 404
            )
            assert stranger.get(f"/api/v1/media/{media_id}").status_code == 404
        checks["history-upload-and-session-ownership-preserved"] = True
        checks["checkpoint-after-restore"] = r.probe(
            1,
            "advance-restored-context",
            "advance-context",
            "--conversation",
            conversation,
            script="probe_phase11_persistence",
        )
        response = client.delete(f"/api/v1/conversations/{conversation}")
        assert (
            response.status_code == 200 and response.json()["cleanup_pending"] is False
        )
        assert client.get(f"/api/v1/conversations/{conversation}").status_code == 404
        assert client.get(f"/api/v1/media/{media_id}").status_code == 404
        checks["deletion-after-restore"] = r.probe(
            1, "deleted-context", "deleted", "--conversation", conversation
        )
        after = r.probe(
            1, "snapshot-after-deletion", "snapshot", script="probe_phase11_persistence"
        )
        assert after["media"]["files"] == 118
        assert (
            r.probe(1, "retrieval-after-deletion", "retrieval")
            == checks["retrieval-before"]
        )
        checks["deletion-preserves-catalog-and-vectors"] = True
    with httpx.Client(
        base_url=r.address(1, "frontend", "3000"), timeout=20, trust_env=False
    ) as client:
        assert client.get("/health/live").status_code == 200
        for category, total in (("restaurants", 210), ("recipes", 109)):
            response = client.get(f"/api/v1/{category}?limit=1")
            assert response.status_code == 200 and response.json()["total"] == total
    checks["frontend-proxy-after-restore"] = True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minilm-root", required=True, type=Path)
    parser.add_argument("--clip-root", required=True, type=Path)
    parser.add_argument("--review-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.minilm_root, args.clip_root, args.review_cache):
        if not path.is_dir():
            parser.error("Required cached input directory missing")
    if not (ROOT / "data/synthetic-recipe-images.zip").is_file():
        parser.error("Restore the recovered recipe ZIP first")
    report = {
        "task": "P11-03",
        "date": datetime.now(ZoneInfo("America/Recife")).date().isoformat(),
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "timezone": "America/Recife",
        "status": "running",
        "steps": [],
        "checks": {},
        "isolation": {
            "provider_calls": 0,
            "owner_dotenv_read": False,
            "langfuse_enabled": False,
            "db_and_mcp_ports": "private",
            "separate_source_target_volumes": True,
        },
        "limitations": [
            "Cached pinned models and original review downloads reused; no paid provider calls",
            "Stored-vector queries verify search adapters; live six-agent follow-ups remain P11-04",
            "Offline quiesced backup only; no online/PITR/cross-version recovery claim",
            "Tracing disabled; optional Cloud retention/deletion operations remain P11-11/12",
        ],
    }
    r = Rehearsal(args, report)
    original = {}
    try:
        original = r.inventory()
        exercise(r, report)
        report["status"] = "passed"
    except BaseException as error:
        report["status"] = "failed"
        report["failure_type"] = type(error).__name__
        raise
    finally:
        failed = report["status"] != "passed"
        try:
            r.cleanup(original)
        except Exception as error:
            report["status"] = "failed"
            report["cleanup"]["failure_type"] = type(error).__name__
            if not failed:
                raise
        finally:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"P11-03 {report['status']}: {args.output}")


if __name__ == "__main__":
    main()
