"""Isolated P01-05 Docker smoke test; no real dotenv or paid providers used."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Build the locked service images first.")
    args = parser.parse_args()
    suffix = secrets.token_hex(6)
    project = f"foodwise-p01-05-{suffix}"
    # Snap Docker cannot read the host's /tmp. These ignored files are removed.
    env_file = ROOT / f".env.compose-smoke-{suffix}"
    override = ROOT / f".env.compose-smoke-{suffix}.yaml"
    salt = base64.b64encode(b"synthetic-salt!!x").decode().rstrip("=")
    digest = base64.b64encode(bytes(range(32))).decode().rstrip("=")
    values = {
        "GROQ_API_KEY": f"synthetic-compose-canary-{suffix}",
        "GROQ_MODEL": "qwen/qwen3.8-27b",
        "GROQ_VISION_MODEL": "qwen/qwen3.8-27b",
        "TAVILY_API_KEY": "",
        "ADMIN_PASSWORD_HASH": f"$argon2id$v=19$m=65536,t=3,p=1${salt}${digest}",
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "FOODWISE_DB_PASSWORD": secrets.token_hex(32),
    }
    env_file.write_text("".join(f"{name}='{value}'\n" for name, value in values.items()))
    env_file.chmod(0o600)
    override.write_text('services:\n  frontend:\n    ports: !override ["127.0.0.1::3000"]\n  backend:\n    ports: !override ["127.0.0.1::8000"]\n')
    base = ["docker", "compose", "--env-file", str(env_file), "--project-name", project, "-f", str(ROOT / "compose.yaml")]
    compose = base + ["-f", str(override)]
    test_env = os.environ | values

    def run(command: list[str], *, timeout: int = 60) -> str:
        result = subprocess.run(command, cwd=ROOT, env=test_env, capture_output=True, text=True, timeout=timeout)
        if result.returncode:
            safe_error = result.stderr
            for value in values.values():
                if value:
                    safe_error = safe_error.replace(value, "[redacted]")
            raise RuntimeError(f"Docker command failed ({result.returncode}): {safe_error[-3000:]}")
        return result.stdout

    def execute(service: str, code: str) -> str:
        return run(compose + ["exec", "-T", service, "python", "-c", code])

    def fetch(url: str) -> tuple[int, bytes]:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    try:
        config = json.loads(run(base + ["config", "--format", "json"]))
        assert set(config["services"]) == {"db", "backend", "mcp", "frontend"}
        for name in ("db", "mcp"):
            assert not config["services"][name].get("ports"), "Private service has a published port"
        for name in ("backend", "frontend"):
            assert all(port["host_ip"] == "127.0.0.1" for port in config["services"][name]["ports"])
        assert not config["services"]["frontend"].get("environment"), "Backend environment reached frontend"
        assert set(config["services"]["mcp"]["environment"]) == {"DATABASE_URL", "MEDIA_ROOT"}
        print("Compose configuration: four services, localhost ports, isolated environments.", flush=True)
        if args.build:
            run(base + ["build", "backend", "frontend"], timeout=1200)
            print("Locked container builds passed.", flush=True)
        run(compose + ["up", "-d", "--wait", "--wait-timeout", "180"], timeout=210)
        raw_status = run(compose + ["ps", "--format", "json"])
        status = json.loads(raw_status) if raw_status.lstrip().startswith("[") else [
            json.loads(line) for line in raw_status.splitlines()
        ]
        assert len(status) == 4 and all(item["Health"] == "healthy" for item in status)
        frontend_url = "http://" + run(compose + ["port", "frontend", "3000"]).strip()
        backend_url = "http://" + run(compose + ["port", "backend", "8000"]).strip()
        assert fetch(frontend_url + "/health/live")[0] == 200
        page_status, page = fetch(frontend_url)
        assert page_status == 200 and b"foodwise-ai" in page
        assert all(value.encode() not in page for value in values.values() if value)
        assert fetch(backend_url + "/api/v1/health/ready")[0] == 200
        execute("backend", """
import asyncio
from fastmcp import Client
async def check():
    async with Client('http://mcp:8001/mcp', timeout=5) as client:
        assert await client.list_tools() == []
        assert await client.list_resources() == []
asyncio.run(check())
""")
        print("All four services healthy; frontend page, API readiness and MCP initialization/discovery passed.", flush=True)
        db_code = """
import os
import json
import psycopg
from pathlib import Path
dsn = os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://', 1)
with psycopg.connect(dsn) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname=current_user')
        assert cursor.fetchone() == (False, False, False, False)
        cursor.execute("SELECT current_setting('server_version'), extversion FROM pg_extension WHERE extname='vector'")
        versions = cursor.fetchone()
        assert versions is not None
        print(json.dumps({'postgresql': versions[0], 'pgvector': versions[1]}))
        cursor.execute("SELECT '[1,2,3]'::vector <=> '[1,2,3]'::vector")
        assert cursor.fetchone() == (0.0,)
        cursor.execute('CREATE TABLE compose_persistence_probe (id integer PRIMARY KEY)')
        cursor.execute('INSERT INTO compose_persistence_probe VALUES (1)')
Path(os.environ['MEDIA_ROOT'], 'compose-persistence-probe').write_text('persistent')
"""
        versions = json.loads(execute("backend", db_code))
        print(f"Verified database versions: PostgreSQL {versions['postgresql']}, pgvector {versions['pgvector']}.", flush=True)
        execute("mcp", """
import os
from pathlib import Path
try:
    Path(os.environ['MEDIA_ROOT'], 'must-not-write').write_text('blocked')
except OSError:
    pass
else:
    raise AssertionError('MCP media mount is writable')
""")
        run(compose + ["down"], timeout=90)
        run(compose + ["up", "-d", "--wait", "--wait-timeout", "180"], timeout=210)
        execute("backend", """
import os
import psycopg
from pathlib import Path
with psycopg.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg://', 'postgresql://', 1)) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SELECT id FROM compose_persistence_probe')
        assert cursor.fetchone() == (1,)
assert Path(os.environ['MEDIA_ROOT'], 'compose-persistence-probe').read_text() == 'persistent'
""")
        print("Limited database role, read-only MCP media and persistence across container recreation passed.", flush=True)
        # Random published ports can change when containers are recreated.
        backend_url = "http://" + run(compose + ["port", "backend", "8000"]).strip()
        run(compose + ["stop", "mcp"])
        assert fetch(backend_url + "/api/v1/health/live")[0] == 200
        response_status, body = fetch(backend_url + "/api/v1/health/ready")
        assert response_status == 503 and json.loads(body)["dependencies"]["mcp"] == "unavailable"
        run(compose + ["start", "mcp", "--wait", "--wait-timeout", "60"], timeout=90)
        run(compose + ["stop", "db"])
        assert fetch(backend_url + "/api/v1/health/live")[0] == 200
        response_status, body = fetch(backend_url + "/api/v1/health/ready")
        assert response_status == 503 and json.loads(body)["dependencies"]["database"] == "unavailable"
        assert all(value.encode() not in body for value in values.values() if value)
        print("Dependency outages return redacted 503 readiness while liveness remains 200.", flush=True)
    except Exception:
        try:
            diagnostics = run(compose + ["logs", "--tail", "40", "db", "mcp", "backend", "frontend"])
            for value in values.values():
                if value:
                    diagnostics = diagnostics.replace(value, "[redacted]")
            print(diagnostics[-5000:], flush=True)
        except Exception:
            print("Service diagnostics unavailable.", flush=True)
        raise
    finally:
        try:
            run(compose + ["down", "--volumes", "--remove-orphans"], timeout=90)
        finally:
            env_file.unlink(missing_ok=True)
            override.unlink(missing_ok=True)
    print("Compose smoke passed; isolated test containers, volumes and configuration removed.")


if __name__ == "__main__":
    main()
