# Local Compose scaffold

For locked host setup, development servers, checks and pending commands, see
the [developer workflow](development.md).

[compose.yaml](../compose.yaml) starts four local services. This is a working
startup scaffold: culinary tools, migrations, ingestion, recommendations, the
API proxy and the full user interface remain their later checklist tasks.

| Service | Runtime and health check | Host access |
| --- | --- | --- |
| `db` | PostgreSQL 16.14 and pgvector, pinned by image digest; readiness requires PostgreSQL and the vector extension. | Internal `db:5432` only. |
| `mcp` | Shared Python 3.12.14 image; FastMCP Streamable HTTP at `/mcp`; `/health/ready` checks PostgreSQL/pgvector and readable media. | Internal `mcp:8001` only. |
| `backend` | FastAPI; `/api/v1/health/ready` checks PostgreSQL/pgvector, writable media and MCP readiness. | `127.0.0.1:8000`. |
| `frontend` | Next.js standalone production server on Node 24.19.0; `/health/live` checks HTTP serving. | `127.0.0.1:3000`. |

Python, Node and uv base images have exact version tags and immutable digests.
The backend image uses uv 0.12.5 and `uv sync --locked --no-dev --no-editable`;
the frontend uses pnpm 12.8.1 and `pnpm install --frozen-lockfile`. Both runtime
images run as non-root users. Repository-context
[exclusions](../.dockerignore) and explicit Dockerfile copy paths keep dotenv
files, course material, data, media and development caches out of the images.
Builds download dependencies; they do not fetch pretrained models or call
Groq/Tavily. The first backend build includes the locked CPU embedding libraries
and can take several minutes.

The verification target is Linux x86_64 with Docker 29.8.0 and Compose 5.5.1.
The database digest pins that upstream platform artifact; other architectures
have not been tested. This host rejects container process execution with
`no-new-privileges` enabled, so the Compose scaffold omits that optional setting.

From the repository root, use Docker Engine and Compose v2.24.4 or newer:

```bash
docker compose version
docker compose config --quiet
docker compose build backend frontend
docker compose up -d --wait --wait-timeout 180
docker compose ps
curl --fail http://127.0.0.1:8000/api/v1/health/ready
curl --fail http://127.0.0.1:3000/health/live
```

Before those commands, fill missing entries in your existing root `.env` using
[.env.example](../.env.example). If no `.env` exists, copy the example first.
Supply a fresh `GROQ_API_KEY`, a single-quoted Argon2id `ADMIN_PASSWORD_HASH`,
and distinct `POSTGRES_PASSWORD` and `FOODWISE_DB_PASSWORD` values. Generate
each database password independently with `openssl rand -hex 32`, then save
the values locally. `FOODWISE_DB_PASSWORD` permits letters, digits, `_` and `-`
because Compose embeds it in a URL; initialization rejects other characters.
Leave Tavily blank to keep trends unavailable. Missing required entries stop
Compose with a setting name and corrective instruction. Avoid plain
`docker compose config` in shared logs: resolved output includes credentials.

Compose explicitly selects each service's environment. It overrides host-run
`DATABASE_URL`, `MCP_SERVER_URL` and `MEDIA_ROOT` with internal service addresses
and `/var/lib/foodwise/media`. The frontend receives no backend configuration;
MCP receives only the database URL and media root. No root dotenv file is
copied or mounted into containers. Configuration validation checks syntax;
startup and health checks do not verify paid provider access.

The `postgres_data` volume persists PostgreSQL, and `media_data` persists media.
Backend media is writable by UID 10001; MCP mounts the same volume read-only.
The database initialization script runs only on a fresh database volume: it
enables pgvector and creates the `foodwise` login with schema privileges but
without superuser, database/role creation or replication privileges. Services
use that login; `postgres` is reserved for initialization/maintenance. Phase 2
will add application migrations; the scaffold creates no catalog tables.

Changing password variables does not rotate credentials in an existing
PostgreSQL volume. If initialization was interrupted or credentials changed,
inspect the database logs and repair that volume deliberately; do not delete
an existing database to resolve configuration errors. The default stack has
no database/MCP host ports. Host-run adapters need separately provisioned
services or an explicit local-only port override.

```bash
docker compose logs --tail 100 backend mcp db frontend
docker compose restart backend
docker compose down
```

`down` stops containers and preserves the named volumes. Health dependency
conditions gate startup using
[Compose's documented readiness behavior](https://docs.docker.com/compose/how-tos/startup-order/).
Liveness stays independent of dependencies; backend/MCP readiness returns a
redacted `503` when local dependencies are unavailable. Healthy means the
scaffold can serve requests, not that recommendations or live trends exist.
The frontend check reports its HTTP availability, while backend readiness
reports backend dependencies. Reserved ports must be free on your machine.

Run the isolated verification from the repository root:

```bash
python infra/verify_compose.py --build
```

[The smoke test](verify_compose.py) creates synthetic settings, a unique Compose
project and random localhost ports. It checks all four services, MCP
initialization/empty discovery, application-role privileges, the read-only
media mount, database/media persistence across container recreation, and
redacted readiness failures during MCP/database outages. It removes only its
own containers, volumes and ignored temporary configuration, including on
failure. It never loads the owner's `.env` or uses paid providers. Omit
`--build` to reuse already built scaffold images. Run it with a host Python
3.12+ interpreter and Docker access; Snap Docker needs permission to access
this repository.

The MCP scaffold follows
[FastMCP HTTP deployment](https://gofastmcp.com/deployment/http) and exposes no
placeholder culinary tools/resources. Its HTTP transport restricts hosts and
origins. FastAPI restricts hosts and enables no cross-origin browser access.
The frontend follows
[Next.js standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output);
full UI/proxy security checks are still required when those features arrive.

The pinned FastMCP client/server currently returns `Method not found` for
protocol ping during this smoke test. Compose uses the custom HTTP readiness
route. Initialization and tool/resource discovery are checked separately;
complete transport compatibility, including ping, remains Phase 6 work.

## Running with limited RAM

[compose.low-memory.yaml](../compose.low-memory.yaml) is an optional override
for the current Phase 1 scaffold. Use both files on every Compose command;
using only the base file removes the limits when containers are recreated.

| Service | RAM ceiling | Adjustment |
| --- | --- | --- |
| PostgreSQL | 256 MiB | 64 MB shared buffers, 2 MB query work memory, 32 MB maintenance memory, 16 MB autovacuum memory, 20 connections, no parallel query workers. |
| FastAPI | 512 MiB | One Uvicorn worker; one thread per configured OpenMP/BLAS library. |
| FastMCP | 512 MiB | Same Python settings. |
| Next.js | 384 MiB | Production server with a 256 MiB V8 old-space heap ceiling. |

The combined container RAM ceilings are 1,664 MiB (1.625 GiB), excluding
Docker, the desktop, IDE and image builds. These are maximum limits, not
reservations or predictions of consumption. The override sets
`memswap_limit` equal to `mem_limit`, so these containers cannot consume host
swap; exhausted limits can cause an OOM kill. Automatic failure restarts are
bounded to three attempts. See [Docker's memory limit semantics](https://docs.docker.com/reference/compose-file/services/#memswap_limit).
This protects against unbounded container growth but cannot prevent unrelated
host applications or builds from exhausting system RAM.

With the existing local `.env` completed, run from the repository root:

```bash
docker compose -f compose.yaml -f compose.low-memory.yaml config --quiet
docker compose -f compose.yaml -f compose.low-memory.yaml up -d --no-build --wait --wait-timeout 180
docker compose -f compose.yaml -f compose.low-memory.yaml ps
docker stats --no-stream
```

If images need building, first make room in RAM and build each image
separately, before starting the stack:

```bash
docker compose -f compose.yaml -f compose.low-memory.yaml build backend
docker compose -f compose.yaml -f compose.low-memory.yaml build frontend
```

The frontend override supplies `FOODWISE_BUILD_NODE_OPTIONS` to its Dockerfile
to cap each build Node process's old-space heap at 1,024 MiB. The production
container's smaller `NODE_OPTIONS` is separate. A Node heap limit does not cap
total process memory or the sum of build workers; service limits do not apply
to Docker builds. Sequential builds reduce competition for RAM. Prefer the
production server over running an additional Next.js development server.

For isolated validation using synthetic credentials and cached images:

```bash
python infra/verify_compose.py --low-memory
```

Add `--build` to verify sequential builds too. The low-memory smoke checks
resolved and enforced limits, actual PostgreSQL settings, cgroup v2 memory
usage, and absence of OOM kills/automatic restarts, as well as the existing
health, discovery, persistence and outage contracts. It uses cgroup v2
accounting on the verified Linux host; other cgroup layouts are unverified.

The [host assessment](memory-assessment.md) records measured hardware and
verification limits. The scaffold does not load pretrained embedding models.
When MiniLM/CLIP retrieval is implemented, measure model loading and inference
peaks before reusing these ceilings. Plan one owner for each resident model,
CPU inference, small batches and bounded embedding jobs. Groq's six agent
roles use remote inference; they do not require six local LLM instances.

This host's `/tmp` is a 3.3 GiB tmpfs, so large temporary files consume
RAM/swap. Keep model caches, media and installation/build scratch files on
the disk-backed workspace or another disk directory. For host-run tools,
create a workspace `.local-tmp/` directory and pass its absolute path as
`TMPDIR` only to commands that need it; keep that directory Git-ignored.
The default Compose media volume already uses disk-backed Docker storage.
Increasing disk-backed swap may provide emergency headroom, but swap is
slower than RAM and does not replace reducing the active workload.
