# Developer workflow

For the complete current application installation, start with the
[clean-checkout release setup](release-setup.md); the steps below cover host
development and the historical scaffold checks.
Use the [local troubleshooting and measured limits](local-operations.md) for
runtime recovery, provider requirements and catalog limitations.

This guide starts from the repository root and covers the FastAPI API,
FastMCP tools/resources and the Next.js meal workspace. Phase 8 supplies the
recommendation/catalog/upload/admin HTTP flows; Phase 9 implements their browser
UI and same-origin proxy. [Frontend evidence](../evaluation/phase9/README.md)
distinguishes real integration from mocked state checks. Health checks make no OpenAI/Tavily calls and load no embedding models.

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
owner configuration. Use a fresh OpenAI key, a locally generated Argon2id
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
probes, logs, restart and shutdown commands. The
[limited-RAM notes](README.md#running-with-limited-ram) record the original
scaffold ceilings; use the release setup's model-aware override for a current
rehearsal and build sequentially. Initialized services serve at `http://127.0.0.1:3000` and
`http://127.0.0.1:8000`; database and MCP ports stay internal.
`docker compose down` preserves named volumes. Preserve them when changing
configuration. Catalog migrations are now explicit host-run operations; see
the migration commands below.

The historical `infra/verify_compose.py` targets the Phase 1 scaffold's empty
MCP discovery and environment assertions. Use the [current clean-checkout
rehearsal](release-setup.md#build-initialize-and-start-compose) for application
setup, with a unique project, separate image tags and localhost port bindings.
It avoids the owner's dotenv file and database/media volumes.

## Host development

Use separate terminals with the working directories stated below. Stop any
Compose backend/frontend using ports 8000/3000 before starting host servers.
The Next.js shell renders independently; chat, catalog and administration use
its same-origin API proxy and require the running backend.

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

MCP validates database/media, optional local model roots and its optional Tavily key; FastAPI requires all backend
settings. Both use shared composition roots and redacted JSON application
logs on stderr, described in the
[P01-08 guide](../backend/README.md#composition-errors-and-logging-p01-08).
MCP exposes Streamable HTTP at `/mcp`; Phase 6 also supplies stdio and culinary
tools/resources. Stop each development server with Ctrl+C.

Start Next.js from `frontend/`, in a shell without backend settings. The
same-origin proxy defaults to `http://127.0.0.1:8000`; for another local API port,
set only the server-side `FOODWISE_API_ORIGIN` in this shell. Compose supplies
`http://backend:8000`. See the [frontend guide](../frontend/README.md#setup-and-local-servers):

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
| `backend/` | `make check` | Ruff lint/format check, strict mypy, OpenAPI drift and pytest. |
| `backend/` | `make api-schema` | Export offline FastAPI OpenAPI; then regenerate frontend contracts. |
| `backend/` | `make test` | Offline suite; database/model cases explicitly skip without their test settings. |
| `backend/` | `make format` | Apply Ruff formatting. Recheck with `make check`. |
| `backend/` | `make test-integration` | Real PostgreSQL contracts; requires an initialized disposable `TEST_DATABASE_URL`. |
| `backend/` | `make provision-test-models` | Seeded local CPU fixtures; requires an ignored `TEST_MODEL_ROOT`. |
| `frontend/` | `pnpm check` | Generated-type drift, Prettier, ESLint, strict TypeScript, Vitest and Node configuration/build contracts. |
| `frontend/` | `pnpm api:generate` | Generate TypeScript from the committed OpenAPI using the pinned generator. |
| `frontend/` | `pnpm lint:fix` | Apply available ESLint fixes. Recheck with `pnpm check`. |
| `frontend/` | `pnpm test:watch` | Watch Vitest component/unit tests. |
| `frontend/` | `pnpm test:e2e:install` | Download locked Chromium once before browser tests. |
| `frontend/` | `pnpm test:e2e` | Build, start and test the production page in Chromium; keep port 3100 free. |
| Repository root | `python scripts/scan_secrets.py` | Redacting source-pattern scan; no matching values are printed. |
| Repository root | `git diff --check` | Detect whitespace errors in changes. |

GNU Make is needed for backend targets. Direct commands are in the
[Makefile](../backend/Makefile); focused commands are in the
[backend quality guide](../backend/README.md#quality-scripts-p01-06).
Frontend `pnpm format` and `pnpm format:check` use pinned Prettier, excluding
generated contracts. `pnpm lint:fix` applies ESLint fixes. See the
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
| Application migrations | Phase 2 adds catalog/provenance, separate vectors, lexical/filter indexes, session/conversation/trends, optimistic versions and cleanup jobs. Explicit host-run commands are below; supported checkpoint setup and cleanup retry are documented in the backend guide. | P02-01 through P02-09 verified; full-corpus ingestion is verified separately in Phase 3. |
| Culinary ingestion | The [Phase 3 seed CLI](../backend/README.md#seed-ingestion-phase-3) is validated, resumable and verified on the full local corpus. | Phase 3, P03-01 through P03-10 verified. |
| Text retrieval | [Phase 4 indexing/search/evaluation](../backend/README.md#multi-source-text-retrieval-phase-4) uses pinned CPU MiniLM and real PostgreSQL. | Phase 4, P04-01 through P04-09 verified. |
| Source audit | `python scripts/phase0_audit.py` from the root is implemented. It requires local course/data/media artifacts and writes Phase 0 reports. It does not populate PostgreSQL. | Phase 0 evidence. |
| Provider capability smoke tests | Explicit opt-in Tavily/OpenAI probes and the [P11-04 live text/image/trend demonstration](live-demo.md) are verified separately from historical provider failures. Health/offline tests make no paid calls. | Scripted live integration and P11-08 local capability acceptance verified; representative quality remains unmeasured. |
| Recommendation/admin API | [Phase 8 API contract](../backend/README.md#phase-8-http-contract) covers browser ownership, SSE, uploads, admin origin/CSRF and atomic CRUD. Backend `MINILM_ROOT`, application migrations and supported checkpoint setup are required for full readiness. | P08-01 through P08-12 verified; Phase 9 browser/proxy evidence is tracked separately. |
| Local release evidence | [P11-01 setup](release-setup.md), [restart/idempotency checks](release-setup.md#migration-ingestion-and-restart-verification-p11-02), [paired restore](backup-restore.md), live/admin demos and portfolio captures have their own evidence. [Operational limits](local-operations.md) distinguish those measurements from unverified capacity. | P11-01–08 verified; [P11-10 paths and registration](release-paths.md) rehearsed separately. Final review and optional Cloud operations remain P11-09/11/12. |

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
The current backend image does not include migration files; use the host
checkout or the read-only setup mounts in the clean-checkout guide. See the [catalog migration guide](../backend/README.md#catalog-persistence-and-migrations-p02-02)
and [provenance guide](../backend/README.md#source-document-and-media-provenance-p02-03)
for identity, nullable fields, rollback behavior and verification. These commands
create the application persistence schema; initialize library checkpoints separately
using the [checkpoint setup guide](../backend/README.md#conversations-profiles-trends-and-checkpoints-p02-06). Test-database bootstrap and source auditing do not
perform culinary ingestion; use the explicit Phase 3 seed CLI after migrations.

A clean checkout includes application source and seed JSON/text. The four course
folders, assignment PDFs and recovered recipe ZIP/109 PNGs are Git-ignored;
they require separate restoration for source auditing and full ingestion.
See the [Phase 0 report](../evaluation/phase0/README.md) for inventory and
unresolved records. Their absence does not block package installation or
offline unit/provider checks. Keep original-history publication review and
unresolved entity review visible in [CHECKLIST.md](../CHECKLIST.md). The
[P11-08 gate](../evaluation/phase11/release-gate.md) records local capability
acceptance; final user review and optional Cloud operations remain separate.
