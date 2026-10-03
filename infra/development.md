# Developer workflow (P01-09)

This guide starts from the repository root and covers the implemented Phase 1
scaffold: FastAPI health routes, an empty FastMCP HTTP server and the Next.js
startup page. Recommendation, catalog, upload and administrator flows remain
planned. Health checks make no Groq/Tavily calls and load no embedding models.

## Locked setup

Use the checked-in versions below. Dependency installation requires network
access; tests use fake providers and local fixtures.

| Tool | Version source | Required version |
| --- | --- | --- |
| Python | [backend/.python-version](../backend/.python-version) | 3.12.14 |
| uv | [backend/pyproject.toml](../backend/pyproject.toml) | 0.12.5 |
| Node.js | [.nvmrc](../.nvmrc) | 24.19.0 |
| pnpm | [frontend/package.json](../frontend/package.json) | 12.8.1 |

Install the pinned uv release using your tool manager. From the repository root:

```bash
cd backend
uv python install 3.12.14
uv sync --locked
uv pip check
uv run --locked python -c "import food_recommender; import fastapi; import fastmcp"
cd ..
```

This creates the ignored `backend/.venv` and installs the default development
group. Keep [uv.lock](../backend/uv.lock) unchanged during normal setup.
See the [backend guide](../backend/README.md) for package boundaries and CPU-only
embedding dependencies. Pretrained weights are separate from installation.

With nvm installed, use this sequence from the repository root. Other Node
managers may install the same pinned version.

```bash
nvm install
nvm use
npm install --global pnpm@12.8.1
cd frontend
pnpm install --frozen-lockfile
pnpm exec next --version
pnpm exec tsc --version
cd ..
```

Keep [pnpm-lock.yaml](../frontend/pnpm-lock.yaml) unchanged during normal setup.
The [frontend guide](../frontend/README.md) explains installation policy and
the separate component, configuration and browser runners.

## Local configuration and Compose

Create a root dotenv file only when one does not already exist:

```bash
test -e .env || cp .env.example .env
```

Fill missing settings using [.env.example](../.env.example) and the
[configuration guide](../backend/README.md#backend-configuration). Keep existing
owner configuration. Use a fresh Groq key, a locally generated Argon2id
administrator hash and distinct database passwords. Tavily may remain blank;
live trends then remain unavailable. Never copy the root dotenv file into
`frontend/` or export backend settings into the frontend shell.

From `backend/`, validate the file without showing its values or connecting to
services:

```bash
uv run --locked python -m food_recommender.infrastructure.config --env-file ../.env
```

The diagnostic exits `0` for valid syntax and `2` for missing/invalid settings.
It does not verify credentials or model capabilities. Server factories read
process settings; host commands below explicitly select the dotenv file using
Uvicorn's `--env-file`. Compose supplies service-specific settings and internal
database/MCP/media addresses itself.

The [Compose guide](README.md) provides prerequisites, builds, startup, health
probes, logs, restart and shutdown commands. This machine should use its
[limited-RAM sequence](README.md#running-with-limited-ram), including sequential
builds. Healthy scaffolds serve at `http://127.0.0.1:3000` and
`http://127.0.0.1:8000`; database and MCP ports stay internal.
`docker compose down` preserves named volumes. Preserve them when changing
configuration. Catalog migrations are now explicit host-run operations; see
the migration commands below.

To verify Compose with isolated synthetic settings, from the repository root:

```bash
python infra/verify_compose.py --low-memory --build
```

Use a host Python 3.12+ interpreter and Docker access. This command builds
sequentially, runs health/discovery/persistence/outage checks, and cleans up its
own disposable containers and volumes. It does not read the owner's dotenv
file. Omit `--build` to reuse scaffold images; omit `--low-memory` on a host
where the ordinary configuration is appropriate.

## Host development

Use separate terminals with the working directories stated below. Stop any
Compose backend/frontend using ports 8000/3000 before starting host servers.
The Next.js page works independently; its same-origin API proxy is pending.

For backend readiness, first provide a reachable PostgreSQL/pgvector service,
a reachable MCP service and an existing writable media directory. Set host
addresses in the root dotenv file: `DATABASE_URL` must reach that database,
`MCP_SERVER_URL` should be `http://127.0.0.1:8001/mcp` for the command below,
and `MEDIA_ROOT` must be an absolute host directory path. Create that directory
deliberately; settings validation does not create it. Base Compose does not
publish a database port; its internal hostnames and container paths do not
resolve from host processes. Separately provision PostgreSQL or explicitly
override its Compose port to publish only on localhost for host development.

Start MCP from `backend/`:

```bash
uv run --locked uvicorn food_recommender.mcp.server:create_app --factory --env-file ../.env --host 127.0.0.1 --port 8001 --reload --no-access-log
```

Start FastAPI from `backend/` in another terminal:

```bash
uv run --locked uvicorn food_recommender.api.main:create_app --factory --env-file ../.env --host 127.0.0.1 --port 8000 --reload --no-access-log
```

MCP validates only database/media settings; FastAPI requires all backend
settings. Both use shared composition roots and redacted JSON application
logs on stderr, described in the
[P01-08 guide](../backend/README.md#composition-errors-and-logging-p01-08).
The scaffold exposes Streamable HTTP at `/mcp`; stdio and culinary tools are
Phase 6 work. Stop each development server with Ctrl+C.

Start Next.js from `frontend/`, in a shell without backend settings:

```bash
pnpm dev
```

The locked Next.js development server regenerates `next-env.d.ts` for its
development types and can create frontend agent-instruction files when it
detects a coding agent. Review generated changes separately before committing.

From another terminal, probe the host servers:

```bash
curl --fail http://127.0.0.1:8001/health/live
curl --fail http://127.0.0.1:8000/api/v1/health/live
curl --fail http://127.0.0.1:3000/health/live
curl --fail http://127.0.0.1:8000/api/v1/health/ready
```

Liveness checks process serving. Readiness returns `503` with dependency names
when database/media/MCP are unavailable. This is expected when starting only
the processes without local dependencies; it does not establish a healthy
stack. `pnpm build` from `frontend/` creates production standalone output;
Compose and Playwright provide the implemented production startup paths.

## Checks and formatting

Run independent suites sequentially on this limited-memory host.

| Working directory | Command | Result or prerequisite |
| --- | --- | --- |
| `backend/` | `make check` | Ruff lint/format check, strict mypy and pytest. |
| `backend/` | `make test` | Offline suite; database/model cases explicitly skip without their test settings. |
| `backend/` | `make format` | Apply Ruff formatting. Recheck with `make check`. |
| `backend/` | `make test-integration` | Real PostgreSQL contracts; requires an initialized disposable `TEST_DATABASE_URL`. |
| `backend/` | `make provision-test-models` | Seeded local CPU fixtures; requires an ignored `TEST_MODEL_ROOT`. |
| `frontend/` | `pnpm check` | ESLint, strict TypeScript, Vitest and Node configuration/build contracts. |
| `frontend/` | `pnpm lint:fix` | Apply available ESLint fixes. Recheck with `pnpm check`. |
| `frontend/` | `pnpm test:watch` | Watch Vitest component/unit tests. |
| `frontend/` | `pnpm test:e2e:install` | Download locked Chromium once before browser tests. |
| `frontend/` | `pnpm test:e2e` | Build, start and test the production page in Chromium; keep port 3100 free. |
| Repository root | `python scripts/scan_secrets.py` | Redacting source-pattern scan; no matching values are printed. |
| Repository root | `git diff --check` | Detect whitespace errors in changes. |

GNU Make is needed for backend targets. Direct commands are in the
[Makefile](../backend/Makefile); focused commands are in the
[backend quality guide](../backend/README.md#quality-scripts-p01-06).
Frontend has no separate formatting script or Prettier configuration;
`pnpm lint:fix` applies only ESLint fixes. See the
[frontend quality guide](../frontend/README.md#quality-scripts-p01-06) for
individual scripts, browser libraries and disk-backed download paths.
Builds and browser tests share `.next`; run them sequentially.

The [CI reproduction guide](ci.md#reproduce-the-database-and-model-checks-locally)
provides disposable database startup, limited-role initialization, model-fixture
provisioning, test settings and cleanup. With both settings supplied, all
database/model cases run; missing settings fail in CI. Fake providers and offline
model fixtures keep these checks independent of paid credentials. Database bootstrap
is exclusively for a fresh `foodwise_test` test service; it is not an
application migration.

On restricted or low-memory environments, select ignored disk-backed caches
before backend installation/checks. From the repository root:

```bash
mkdir -p .local-tmp/uv-cache .local-tmp/scratch
export UV_CACHE_DIR="$PWD/.local-tmp/uv-cache"
export TMPDIR="$PWD/.local-tmp/scratch"
```

These optional settings avoid a read-only default uv cache and large RAM-backed
temporary files. Reapply them in later shells. Tests require local subprocess
and loopback permissions; resolve sandbox denials before assessing results.

## Migration, ingestion and release availability

| Operation | Current status | Planned checklist task |
| --- | --- | --- |
| Application migrations | Phase 2 adds catalog/provenance, separate vectors, lexical/filter indexes, session/conversation/trends, optimistic versions and cleanup jobs. Explicit host-run commands are below; supported checkpoint setup and cleanup retry are documented in the backend guide. | P02-01 through P02-09 verified; ingestion remains Phase 3. |
| Culinary ingestion | The [Phase 3 seed CLI](../backend/README.md#seed-ingestion-phase-3) is validated, resumable and verified on the full local corpus. | Phase 3, P03-01 through P03-10 verified. |
| Text retrieval | [Phase 4 indexing/search/evaluation](../backend/README.md#multi-source-text-retrieval-phase-4) uses pinned CPU MiniLM and real PostgreSQL. | Phase 4, P04-01 through P04-09 verified. |
| Source audit | `python scripts/phase0_audit.py` from the root is implemented. It requires local course/data/media artifacts and writes Phase 0 reports. It does not populate PostgreSQL. | Phase 0 evidence. |
| Provider capability smoke tests | No live setup/smoke command exists. Health and offline tests do not validate Groq model access or dated Tavily evidence. | P06-12, P07-01 and P07-14. |
| Full clean-checkout release | Local media/course recovery, application migrations, ingestion and acceptance flows remain required. | P11-01 through P11-09. |

From `backend/`, preview the implemented application migrations without connecting:

```bash
uv run --locked alembic upgrade head --sql
```

For an intended PostgreSQL database, explicitly export `DATABASE_URL`, then run
from `backend/`:

```bash
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

Migrations read only the process environment and require no provider credentials;
they do not load the root dotenv file or run automatically at application startup.
The current backend image does not include the migration files; use the host
checkout. See the [catalog migration guide](../backend/README.md#catalog-persistence-and-migrations-p02-02)
and [provenance guide](../backend/README.md#source-document-and-media-provenance-p02-03)
for identity, nullable fields, rollback behavior and verification. These commands
create the application persistence schema; initialize library checkpoints separately
using the [checkpoint setup guide](../backend/README.md#conversations-profiles-trends-and-checkpoints-p02-06). Test-database bootstrap and source auditing do not
perform culinary ingestion; use the explicit Phase 3 seed CLI after migrations.

A clean checkout includes scaffold source and seed JSON/text. The four course
folders, assignment PDFs and recovered recipe ZIP/109 PNGs are Git-ignored;
they require separate restoration for source auditing and later full ingestion.
See the [Phase 0 report](../evaluation/phase0/README.md) for inventory and
unresolved records. Their absence does not block scaffold installation or
offline unit/provider checks. Keep original-history publication review and
unresolved mappings visible in [CHECKLIST.md](../CHECKLIST.md); Phase 1
completion does not satisfy the later application release gate.
