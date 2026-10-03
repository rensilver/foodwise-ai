# Food Recommendation Capstone — Development Checklist

## How to use this tracker

The architecture and implementation rules live in [AGENTS.md](AGENTS.md). This checklist tracks the planned application, not completion of the course exercises. All implementation items start unchecked: existing notebook output does not establish that the new application works.

Use stable task IDs when recording work. Mark an item `[x]` only after its behavior is implemented and the stated checks pass. Preserve the user's marks. Record commands/results, relevant artifact paths, and unresolved limitations in each phase's evidence field; never include keys, raw personal profiles, or credentials. A parent phase is complete only when its exit criterion is satisfied. Do not mark a phase complete because a degraded demonstration ran.

The first release is local, English-language, and includes all six agents, multimodal retrieval, live trends and local CRUD. See the deferred section for work outside v1. Independent scaffolding can continue while source recovery or owner-led credential rotation is pending; blocked tasks remain visible.

## Phase 0 — Baseline, credentials, and source recovery

**Prerequisites:** reviewed AGENTS.md and preserved existing user changes.

**Outputs:** sanitized working sources, source manifest/reconciliation report, validated media inventory.

**Verification:** safe secret scan, source counts/relationships, archive integrity and image identity checks.

- [x] P00-01 Record all 35 original artifact slots, hashes for available nonsecret copies, roles and exclusions; preserve course originals and attribution.
- [x] P00-02 Have the credential owner revoke/rotate the exposed Groq credential; record completion without capturing its value or testing the old key.
- [x] P00-03 Remove credential literals from both workflow notebook copies and inspect stored outputs for leaked secrets.
- [x] P00-04 Ignore real environment files, add safe configuration examples, and remove any tracked environment file from this repository's Git index while preserving the local file.
- [x] P00-05 Run a redacting secret scanner over the working tree and identify historical exposure; document any history remediation separately without automatically rewriting Git history.
- [x] P00-06 Validate the baseline: 204 unique restaurant IDs, 109 recipe IDs, ten review IDs, one synthetic user, nine review image references/captions, and no orphan review links.
- [x] P00-07 Map all 210 raw restaurant paragraphs to existing/new/unresolved records; review duplicates and omissions, preserve existing IDs, and document every discrepancy.
- [x] P00-08 Validate the owner-recovered recipe ZIP against notebook naming; verify bytes, ZIP integrity, bounded safe member paths and decoded image formats.
- [x] P00-09 Build the `recipe{id}.png` media manifest; check numeric IDs, duplicates, missing/extra files and image-to-recipe associations without list-order pairing.
- [x] P00-10 Confirm usable recipe imagery for the full multimodal release; keep unrecovered review URLs and unlinked placeholder imagery explicitly documented.

**Exit criterion:** source coverage is reconciled or explicitly quarantined, recipe imagery is available and mapped, and exposed credentials are revoked with safe working-tree configuration. Any remaining blocker stays open for the release gate.

**Evidence / blockers:** See [Phase 0 report](evaluation/phase0/README.md) and its JSON manifests. `python scripts/phase0_audit.py` verified 204/109/10 source records, aligned 204 of 210 restaurant paragraphs, decoded 109 unique ID-matched PNGs (215,942,257 bytes), and verified the owner-recovered ZIP's paths, bounds, CRCs and byte-for-byte image hashes. Six paragraphs have no structured record; 16 same-name/location pairs need entity review. `python scripts/scan_secrets.py` found zero patterns in local source copies. The owner confirmed old Groq key revocation/replacement on 2026-10-02. Original-repository credential history still needs publication review. The ZIP, images, PDFs and four course folders are local and Git-ignored, so clean-checkout recovery must be documented later.

## Phase 1 — Project foundation and developer workflow

**Prerequisites:** baseline recorded; unresolved Phase 0 external blockers may remain visible.

**Outputs:** backend/frontend scaffolds, locked dependencies, Compose configuration and quality scripts.

**Verification:** clean dependency install, service boot, lint/type checks and CI dry run without paid providers.

- [x] P01-01 Scaffold the approved backend package, frontend feature folders, evaluation directory and infrastructure configuration without moving course artifacts.
- [x] P01-02 Pin Python 3.12 and compatible Node/pnpm versions; resolve and commit `uv.lock` and `pnpm-lock.yaml` with compatible framework/provider packages.
- [x] P01-03 Add validated configuration for Groq text/vision models, Tavily, PostgreSQL, MCP, media and local administrator password hash; preserve the configured Groq text-model default.
- [x] P01-04 Add safe `.env.example` entries and actionable missing-configuration messages; ensure no secrets reach `NEXT_PUBLIC_*` or client bundles.
- [x] P01-05 Define PostgreSQL/pgvector, backend, FastMCP and Next.js Compose services, volumes and health checks; publish required ports only on localhost.
- [x] P01-06 Add Ruff, mypy, pytest/async testing, ESLint, TypeScript checks, Vitest/Testing Library and Playwright scripts with documented working directories.
  - [x] P01-06-01 Add locked quality tooling and documented commands; verify backend lint/format/type/tests, frontend lint/type/component/configuration tests, and Playwright test discovery.
  - [x] P01-06-02 Install the Chromium revision required by locked Playwright (and any missing Linux browser libraries), run `pnpm test:e2e` from `frontend/`, and record a passing production-browser journey before completing P01-06.
- [x] P01-07 Create CI for backend/frontend checks and real PostgreSQL/pgvector integration tests, using fake external providers and pre-provisioned model fixtures.
- [x] P01-08 Add dependency injection/composition roots, structured redacted logging, and shared typed error conventions.
- [x] P01-09 Document runnable setup, test, formatting, migration, ingestion and development commands as each is implemented; distinguish placeholders from working commands.

**Exit criterion:** a clean checkout can install locked dependencies and start healthy local scaffolds; configured quality checks run without Groq/Tavily calls.

**Evidence / blockers:** P01-01 verified on 2026-10-02: [repository overview](README.md), [backend](backend/README.md), [frontend](frontend/README.md), [evaluation](evaluation/README.md), and [infrastructure](infra/README.md) document the scaffold and boundaries. Added project metadata, all eight backend subpackages, frontend feature folders, migration/test/evaluation placeholders, root Docker build exclusions, and development-cache Git ignores. Direct imports of all nine Python packages passed without external dependencies; TOML/JSON parsing, 16 placeholder directories, 46 local Markdown links, code fences, 134 unique checklist IDs, and the AGENTS.md size limit passed. All 34 available Phase 0 artifact hashes are unchanged. `python scripts/scan_secrets.py` scanned 44 source files with zero findings; `git diff --check` passed. Imports were checked using the host Python 3.13.13, not a configured Python 3.12 environment. Dependency installation/locks, runtime pins, service startup, Compose, and quality tooling were pending at that scaffold checkpoint.

P01-02 verified on 2026-10-02 on Linux x86_64: pinned Python 3.12.14 ([backend runtime](backend/.python-version)), Node 24.19.0 ([Node runtime](.nvmrc)), pnpm 12.8.1, and uv 0.12.5. [Backend metadata](backend/pyproject.toml) pins 18 direct dependencies and the Hatchling build backend; [uv.lock](backend/uv.lock) resolves 141 packages across platform branches. Linux installed 135 packages with CPU-only `torch==2.14.1+cpu`; the lock contains no NVIDIA/CUDA dependencies. [Frontend metadata](frontend/package.json) pins 15 direct dependencies including Next.js 16.3.8, React 19.3.0, Tailwind 4.3.3, TypeScript 5.9.3, Node 24 types, and shadcn/Radix utilities; [pnpm-lock.yaml](frontend/pnpm-lock.yaml) contains 177 application graph entries and installed 124 packages. [pnpm settings](frontend/pnpm-workspace.yaml) enforce runtime versions, exact saves, and strict peers; `pnpm config get` confirmed all three settings are enabled.

Fresh `uv sync --locked` and `pnpm install --frozen-lockfile` passed using temporary download caches/tools; an offline frozen frontend install also passed. `uv pip check` found no conflicts; `uv lock --check --offline` passed. Inline offline smoke checks passed for all nine project packages, framework/provider imports, in-process FastAPI HTTP, FastMCP construction, LangGraph compilation/execution, async SQLAlchemy/psycopg adapter construction, and a tiny randomly initialized CPU CLIP forward pass. The initial broader backend smoke stalled under the process sandbox and was interrupted; its bounded rerun outside that sandbox passed. No database connection, Groq/Tavily call, or pretrained-model download was made. Frontend checks passed for Next/TypeScript versions, React SSR, Radix/Lucide/utilities, native SWC TypeScript compilation, and Tailwind/PostCSS compilation. `uv build --offline` produced an sdist and wheel in temporary storage; the wheel contains all nine packages and the sdist excludes environment files/course data. Manifest-to-lock checks, 63 local Markdown links, code fences, 134 unique checklist IDs, and the AGENTS.md size limit passed. The source scanner found zero findings across 44 files; an additional redacting scan of seven runtime/manifest/lock files also found zero. `git diff --check` passed. Other operating systems, application startup, provider/model capabilities, and quality tooling are unverified and remain covered by P01-03 through P01-09 and later phases; the Phase 1 exit gate remains open.

P01-03 verified on 2026-10-02 with Python 3.12.14: [backend configuration](backend/src/food_recommender/infrastructure/config.py) validates uppercase environment names, required Groq credentials, independently configurable text/vision identifiers (both default to `qwen/qwen3.8-27b`), optional Tavily credentials, PostgreSQL/psycopg URLs, HTTP(S) MCP endpoints, absolute media roots and bounded Argon2id v19 administrator hashes. Settings are immutable, loaded explicitly without caching or implicit dotenv discovery, and support opt-in dotenv files with environment precedence. Keys, database URLs and hashes are masked; the loader's typed validation failures omit supplied values. [Backend documentation](backend/README.md) records the contracts and runnable test command. Red/green verification began with a missing-module failure; a later regression test caught and corrected unintended lowercase environment support. `uv run --locked --offline python -m unittest discover -s tests/unit -p 'test_config.py' -v` passed all 13 offline [configuration tests](backend/tests/unit/test_config.py), covering defaults, overrides, missing/invalid values, secret redaction, dotenv precedence, immutability, fresh loads and import/loading without service dependencies or media creation. No dependencies/locks or real environment files changed; no provider calls, service connections or model downloads were made. Service readiness, credential/model capability checks, password verification, configuration examples and shared quality tooling remain their later checklist tasks; the Phase 1 exit gate remains open.

P01-04 verified on 2026-10-02: [.env.example](.env.example) now documents required blank secrets, optional unavailable trends, host-only PostgreSQL/MCP examples, an absolute media path and quoted Argon2id hashes. [Backend configuration](backend/src/food_recommender/infrastructure/config.py) adds field-specific corrective guidance and an offline `python -m food_recommender.infrastructure.config [--env-file PATH]` check with redacted status/errors and exit codes 0/2. [Next.js configuration](frontend/next.config.mjs) rejects every `NEXT_PUBLIC_*` name and all eight backend settings from the frontend process/dotenv files, with names-only diagnostics and no exported `env` values. [Setup documentation](backend/README.md#local-setup-and-offline-diagnostics) and [frontend guidance](frontend/README.md) explain separate process environments and runnable checks.

Red/green checks verified missing guidance, incomplete examples and the absent frontend guard before implementation. The isolated production build additionally exposed an unprefixed synthetic secret in server-rendered HTML; the backend-variable guard now rejects that build before rendering. `uv run --locked --offline python -m unittest discover -s tests/unit -p 'test_config.py' -v` passed all 17 backend tests with Python 3.12.14. `node --test tests/configuration.test.mjs` passed all five frontend tests with Node 24.19.0/Next.js 16.3.8, including actual Next.js dotenv loading in dev/build, per-variable rejection, redaction, rejected secret-bearing builds, and a clean temporary Webpack production build whose browser JavaScript and HTML contain no synthetic canary. Node subprocess tests required execution outside the process sandbox; automatic approval allowed the offline test runs. The redacting source/config scan and documentation checks passed, and `git diff --check` passed. Local `.env` and dependency locks were untouched; no paid provider calls, service connections or model downloads occurred. The production build was an isolated test fixture, not the planned application. Full UI/proxy bundle checks remain necessary as those features are implemented; P01-05 onward and the Phase 1 exit gate remain open.

P01-05 verified on 2026-10-02 on Linux x86_64 with Docker 29.8.0/Compose 5.5.1: [Compose](compose.yaml) defines PostgreSQL/pgvector, backend, separate HTTP FastMCP and Next.js services with persistent database/media volumes, dependency health gates and only `127.0.0.1:8000`/`127.0.0.1:3000` published. [Backend](infra/backend.Dockerfile) and [frontend](infra/frontend.Dockerfile) images pin Python 3.12.14, uv 0.12.5 and Node 24.19.0 by version/digest, install locked dependencies, cache downloads and run as non-root users. PostgreSQL 16.14/pgvector 0.8.6 were measured in the pinned database image; fresh-volume initialization creates the vector extension and a limited application login. MCP receives only database/media settings and mounts media read-only; frontend receives no backend secrets. Added minimal startup pages/factories, bounded local readiness probes, safe database-password examples and [setup/verification guidance](infra/README.md).

Red/green checks began with a missing API module; an additional regression test caught and corrected malformed MCP readiness handling. All 22 offline backend configuration/health/HTTP MCP tests passed; all five frontend environment/build tests passed, including guards for both new database password names. Strict TypeScript checking passed. Pinned image builds passed, and `python infra/verify_compose.py` passed against those images with synthetic configuration: four healthy services, frontend page/API health, MCP initialization/empty tool/resource discovery, real vector cosine operations, limited database privileges, read-only MCP media, database/media persistence across container recreation, and redacted 503 readiness during MCP/database outages with 200 liveness. The test removed its isolated containers/volumes/configuration. Source/infrastructure secret scans, documentation checks and `git diff --check` passed. The owner's `.env`, dependency locks and course artifacts were untouched; no Groq/Tavily calls or model downloads occurred.

Host compatibility notes are documented: Docker rejects process execution with optional `no-new-privileges` enabled here, so the scaffold omits it; the pinned MCP client/server returns `Method not found` for protocol ping, while initialization/discovery and custom HTTP readiness work. Complete MCP transport compatibility remains Phase 6 work. Other architectures, application migrations/features and P01-06 onward remain unverified/planned; the Phase 1 exit gate remains open.

P01-06 implementation checkpoint on 2026-10-02: [backend quality targets](backend/Makefile) and [configuration](backend/pyproject.toml) add locked Ruff, strict mypy, pytest and explicitly loaded pytest-asyncio. Runtime scaffolds now have type annotations, existing Python files are Ruff-formatted, and two health tests exercise native async pytest contracts. [Frontend scripts](frontend/package.json) add ESLint, TypeScript, Vitest/Testing Library and Playwright commands with locked dependencies, separate test discovery and a standalone production-server launcher. The [backend](backend/README.md#quality-scripts-p01-06) and [frontend](frontend/README.md#quality-scripts-p01-06) guides document working directories, setup and test limitations.

`make check` from `backend/` passed Ruff lint, formatting for 16 files, strict mypy for 13 runtime files and all 22 pytest tests. `uv lock --check --offline` passed; `uv pip check` found no conflicts. From `frontend/`, lint and strict TypeScript passed, Vitest passed one component test, and `pnpm test:config` passed all five configuration/security contracts. Backend ASGI tests stalled and frontend subprocess tests failed under the process sandbox; bounded reruns outside it passed. A frozen frontend install using the existing temporary package store passed (513 packages reused, zero downloaded); the initial offline attempt with the default store lacked cached tarballs, and the local installation was restored afterward. `pnpm exec playwright test --list` discovered one Chromium journey. `pnpm test:e2e` built the production application and started the standalone server, then failed at browser launch because the required `chromium_headless_shell-1243` executable was absent from the temporary browser cache. No browser assertions ran; P01-06-02 and the parent P01-06 remain open. The source scanner found zero findings across 53 files; an extended redacting scan covering runtime/test/configuration/lock files found zero findings across 57 files. Document checks passed for 63 local links, balanced code fences, unique task IDs and the AGENTS.md size limit; `git diff --check` passed. No paid provider calls or pretrained-model downloads occurred; CI and real PostgreSQL integration coverage remain P01-07.

Local memory assessment on 2026-10-02: the host exposes 6.538 GiB RAM and 4 GiB swap; the initial snapshot had only 871 MiB available RAM and almost no free swap. The optional [low-memory Compose override](compose.low-memory.yaml) passed `python infra/verify_compose.py --low-memory` against cached images with synthetic credentials. Measured post-startup cgroup memory totaled 430.1 MiB across PostgreSQL, FastAPI, FastMCP and production Next.js; actual container limits and PostgreSQL settings were verified, and the existing health/discovery/persistence/outage checks passed without OOM kills or automatic restarts. [The assessment](infra/memory-assessment.md) and [setup guide](infra/README.md#running-with-limited-ram) distinguish startup observations from peaks and future MiniLM/CLIP requirements. This does not establish full recommendation capacity or close any phase exit gate; owner configuration and existing workloads were preserved.

The subsequent `python infra/verify_compose.py --low-memory --build` passed sequential locked backend/frontend builds (including the frontend's optional 1,024 MiB build heap ceiling), then all isolated smoke scenarios again with no OOM kills or automatic restarts; its post-startup snapshot totaled 350.4 MiB. Document checks passed for 55 local links, balanced code fences and scratch-directory exclusions; Python compilation, the redacting source scan (54 files, zero findings) and `git diff --check` passed. Runtime snapshots are not peak measurements and do not cover future embedding/recommendation workloads.

P01-06-02 and P01-06 completed on 2026-10-02: using Node 24.19.0, pnpm 12.8.1 and locked Playwright 1.63.0, `pnpm test:e2e:install` downloaded Chromium and Chrome Headless Shell revision 1243 (153.0.8010.12), plus FFmpeg revision 1011, into ignored disk-backed `.local-tmp/playwright/`. The installed system libraries were sufficient; no OS packages were installed. `pnpm test:e2e` from `frontend/` passed the production [Chromium journey](frontend/tests/e2e/startup.spec.ts): one test passed in 28.3 seconds, including the application build and standalone server startup. Assertions verified the product title/heading, visible main content, English markup, successfully served browser JavaScript, absence of page errors and the liveness response. The server shut down afterward. Installation and test execution required network/subprocess access outside the process sandbox; automatic approval allowed both. The run used disk-backed scratch storage, disabled Next.js telemetry and a 1,024 MiB Node old-space ceiling. [Frontend instructions](frontend/README.md#quality-scripts-p01-06) document reusing the same browser-cache path for installation and later runs. Document checks and `git diff --check` passed. Dependencies/locks, owner configuration and course artifacts were unchanged; no Groq/Tavily calls or pretrained-model downloads occurred. The passing browser journey completes the remaining P01-06 verification alongside the earlier P01-06-01 results; CI, full application journeys and the Phase 1 exit gate remain open.

P01-07 verified locally on 2026-10-02: [GitHub Actions workflow](.github/workflows/ci.yml) adds separate Ubuntu 24.04 backend/frontend jobs for pushes, pull requests and manual dispatch, with commit-pinned actions, locked installations, read-only repository permissions and bounded job times. Backend CI provisions the existing digest-pinned PostgreSQL 16/pgvector 0.8.6 image with a limited test login, generates tiny seeded CPU model files before testing, then runs `make check` and the redacting source scan. Frontend CI runs `pnpm check`, installs the locked Chromium revision/system libraries and runs the production browser journey. [The CI guide](infra/ci.md) documents the actual commands, fixtures, disposable database setup and cleanup.

Red/green verification first produced two failures and six missing-fixture errors for unguarded external DNS, absent saved models and missing provider/database support. [Shared test fixtures](backend/tests/conftest.py) now serve canned Groq/Tavily HTTP responses, block external Python DNS/socket connections and require localhost `foodwise_test` database settings. [Offline SDK/model contracts](backend/tests/contract/test_offline_fixtures.py) exercise both provider clients with synthetic credentials and load local random BERT/CLIP fixtures with `local_files_only=True`; 384-dimensional text hidden states and 512-dimensional CLIP projections are finite and CPU-only. Offline flags prevent pretrained downloads. Missing database/model settings fail in CI; ordinary local runs explicitly skip those optional suites. These random fixtures verify interfaces, not relevance or the future pretrained retrieval models.

`make check` from `backend/` with CI settings passed Ruff lint/formatting (21 files), strict mypy (13 runtime files) and all 32 tests in 8.77 seconds, including four [real PostgreSQL/pgvector contracts](backend/tests/integration/test_postgres.py): limited-role privileges/versions, vector adapter roundtrips and cosine ordering in both dimensions, transaction rollback preserving prior data after a partial invalid write, and actual async database/media readiness. Real database testing caught and corrected assumptions about temporary-table permission and the locked adapter's `Vector` return type; the test role keeps the Compose permission policy. Test table creation/data rolled back, a subsequent query found zero public tables, and the disposable container/storage were removed. A normal local `make test` without integration/model settings passed 27 tests with five explicit skips in 2.76 seconds. From `frontend/`, `pnpm check` passed lint, TypeScript, one component test and all five configuration/build tests; `pnpm test:e2e` with CI settings passed one production Chromium journey in 28.3 seconds. Official actionlint 1.7.12 (release checksum verified) accepted the workflow, and pinned action inputs/hashes were checked against their official repositories. Source scanning found zero findings across 62 files; documentation checks and `git diff --check` passed. Locked backend dependencies were restored after discovering a missing existing interpreter, using disk-backed workspace caches; dependency manifests/locks, owner configuration and course artifacts were unchanged. Network installation, local Docker and subprocess test execution used automatically approved sandbox escalations. No paid provider calls or pretrained-model downloads occurred. Hosted GitHub execution awaits a push; local validation does not claim a hosted green run. P01-08/P01-09 and the Phase 1 exit gate remain open.

P01-08 verified on 2026-10-02: [composition roots](backend/src/food_recommender/composition.py) bind validated settings to the implemented application readiness port without connecting services or loading models. Both factories accept explicit services/runtime dependencies; FastAPI routes support [dependency overrides](backend/src/food_recommender/api/dependencies.py), and MCP uses its separate database/media settings with read-only media checks. [Shared application failures](backend/src/food_recommender/application/errors.py) use framework-independent codes. The [HTTP boundary](backend/src/food_recommender/infrastructure/http.py) maps application/unexpected failures to fixed Pydantic error envelopes with request IDs; API validation and HTTP errors omit input/detail text. Existing health payloads and native MCP JSON-RPC responses retain their contracts. Cancellation and failures after headers propagate; future SSE/tool-specific error handling remains later work.

[JSON logging](backend/src/food_recommender/infrastructure/observability.py) configures existing Python SDK/Uvicorn handlers on stderr with allowlisted events, UUIDs, codes and numeric metrics. Messages, exception/stack text, URLs, headers, paths, profile/image content and arbitrary extras are omitted. Request IDs are generated independently of incoming headers; request/run context resets after completion/failure/cancellation and stays isolated during overlapping requests. Clock, ID generation and logging can be injected. Run/token/search/retrieval metric fields are supported for future orchestration, not measured by the health scaffold. Unknown SDK/server messages become limited `diagnostic` records; arbitrary direct writes are outside the Python logging formatter. [Backend guidance](backend/README.md#composition-errors-and-logging-p01-08) documents wiring, mappings, process logging and extension boundaries.

Red verification failed collection because the new dependency module was absent. After implementation, `make check` passed Ruff lint, formatting (29 files), strict mypy (20 runtime files), and 45 tests in 8.20 seconds with real disposable PostgreSQL/pgvector and pre-provisioned offline model fixtures, without skips. Database objects rolled back; a subsequent query found zero public tables, and the disposable container/storage were removed. A final expanded suite added the after-headers failure contract and checked framework HTTP-detail redaction: local `make check` passed 41 tests with five explicit database/model skips in 2.93 seconds. All 14 [foundation contracts](backend/tests/unit/test_foundation.py) passed, covering dependency replacement, liveness independence, code/status/retryability mapping, synthetic private-data redaction, server/SDK logging, injected duration/IDs, cancellation, streaming failure propagation and concurrent context isolation. `python infra/verify_compose.py --low-memory --build` passed locked sequential builds and all four-service health/discovery/persistence/outage scenarios without OOM kills or automatic restarts, then removed isolated containers/volumes/configuration. Live inspection of those Uvicorn processes verified empty logging stdout and JSON stderr: 13 backend records and 23 MCP records, with four observed UUID/duration requests in each snapshot. The source scan, actionlint, document checks and `git diff --check` passed. Sandbox escalation for local Docker/process tests was automatically approved. Owner configuration, course artifacts and dependency manifests/locks were unchanged; no paid provider calls or pretrained-model downloads occurred. P01-09 and the Phase 1 exit gate remain open; hosted CI still awaits a push.

P01-09 verified on 2026-10-02: the [developer workflow](infra/development.md), linked from the root/backend/frontend/infrastructure READMEs, collects pinned setup, configuration diagnostics, Compose verification, host development, formatting and test commands with their working directories and prerequisites. Its availability table explicitly marks application migrations, culinary ingestion and live provider smoke commands as unimplemented; it distinguishes the working source audit and disposable test-database bootstrap from ingestion/migrations. Clean-checkout media/course recovery and release blockers remain visible. No new runtime commands or dependencies were introduced.

Document checks passed for 11 Markdown files, 173 relative links/anchors, ten Bash blocks, 136 unique checklist IDs and the 32 KiB root instruction budget (32,353 bytes). Command inventory matched the Makefile/package scripts, Uvicorn/Compose-verifier CLI options and the actual migration/ingestion scaffolds. Cached `uv sync --locked --offline` and `uv pip check` passed with 145 installed packages; uv, Node, pnpm, Next.js and TypeScript version probes matched the pins. Temporary synthetic dotenv checks returned the documented exit codes `0`/`2`. Both documented Uvicorn factory commands started with `--reload --env-file`, served liveness `200` and returned readiness `503` with the absent database and available temporary media correctly identified. The API smoke used a free port to preserve the existing service on 8000. `pnpm dev` served frontend liveness `200` in a separate environment. All smoke processes, settings, media and logs were cleaned up; Next-generated source changes were restored. The source scan and `git diff --check` passed. Local process/network checks used automatically approved sandbox escalation. No owner configuration, course artifacts or dependency locks changed; no paid provider calls or model downloads occurred. The P01-08 pre-commit `make check` rerun passed 41 tests with five explicit unconfigured database/model skips in 3.01 seconds. Documentation work did not rerun unrelated application/browser suites. All Phase 1 tasks are marked complete on their recorded scaffold evidence; hosted CI still awaits a push, and the full clean-checkout application release remains Phase 11 work.

Phase 1 closure audit on 2026-10-03 against committed revision `8a6fd90`: **the local scaffold exit criterion is satisfied; all P01 completion marks are supported.** A separate checkout made from `git archive HEAD` installed 145 backend packages with `uv sync --locked --offline`; `uv pip check`, `uv lock --check --offline` and runtime imports passed. A fresh `pnpm install --frozen-lockfile` downloaded/installed 513 packages into that checkout, preserving both lockfiles. Its production Chromium startup journey passed (one test, 32.2 seconds), confirming a fresh frontend build and boot. Working-tree checks passed backend Ruff lint/format, strict mypy (20 runtime files) and **46 tests with zero skips**, including four real disposable PostgreSQL/pgvector tests and local CPU model/fake-provider contracts; frontend ESLint, TypeScript, one component test, all five configuration/build tests and the production Chromium journey also passed. `python infra/verify_compose.py --low-memory` passed four-service startup, MCP discovery, database/media persistence and dependency-outage checks using cached images; audit images were not rebuilt. Actionlint and the redacting source scan passed (71 files, zero findings). Process/socket tests required automatically approved execution outside the restricted process sandbox. All audit containers and the temporary checkout/install store were removed; existing services, owner configuration, course artifacts and dependency locks were preserved. No paid provider calls or pretrained-model downloads occurred. Hosted Actions execution remains unverified, as already documented; Phase 1 requires a CI dry run, while full application/release verification remains in later phases.

## Phase 2 — Domain contracts and PostgreSQL persistence

**Prerequisites:** Phase 1 and reviewed source mappings from Phase 0.

**Outputs:** typed domain/API concepts, migrations, repository adapters and transaction boundaries.

**Verification:** real database tests for constraints, migrations, identity, ownership and transaction failure.

- [x] P02-01 Define typed preferences, explicit/inferred constraints, candidate evidence, expert outcomes, recommendations, citations and progress events.
- [x] P02-02 Model restaurants, recipes and reviews with stable identities, source-ID uniqueness and valid foreign keys; keep unknown fields nullable.
- [x] P02-03 Add source-record, document and media provenance including content hashes, timestamps, raw payloads and generation/import attribution.
- [x] P02-04 Create separate text `vector(384)` and image `vector(512)` storage with embedding model/revision/input hashes; enable pgvector through migration.
- [x] P02-05 Add PostgreSQL full-text fields and ordinary filter indexes; keep exact vector search as the initial implementation.
- [x] P02-06 Add conversations, profiles, session ownership and trend cache persistence; initialize PostgreSQL checkpoint tables through the supported LangGraph path.
- [x] P02-07 Implement repository and transaction ports/adapters, optimistic record versions and atomic catalog/document/vector writes.
- [x] P02-08 Test fresh migrations, rollback on failed writes, duplicate-ID rejection, foreign-key enforcement, version conflicts and session isolation.
- [x] P02-09 Define and test deletion of conversation-owned messages/checkpoints/uploads without deleting shared catalog data.

**Exit criterion:** typed domain rules and persistence contracts are independently testable; migrations and integrity/ownership tests pass against PostgreSQL/pgvector.

**Evidence / blockers:** P02-01 verified on 2026-10-03 with Python 3.12.14:
[domain contracts](backend/src/food_recommender/domain/) define frozen standard-library
types for preferences and constraint provenance/strength, category-qualified IDs,
source-backed candidate evidence/citations, all six role results, explicit
success/unavailable/failure outcomes, recommendations and the five UUID-scoped
event types. [Application adapters](backend/src/food_recommender/application/contracts.py)
validate untrusted JSON strictly, reject nested extra fields, preserve domain
types and generate schemas without duplicating field definitions. Domain
invariants bound retrieval to three attempts and 20 unique candidates/category,
and recommendations to five unique items/category. Reference validation rejects
unknown IDs, citations from other candidates and conflicting assessments; hard
restrictions reject absent/unknown compliance. Dated web evidence is required
for trend claims; source dates, absent modalities and missing metadata retain
their unknown states. [Backend guidance](backend/README.md#shared-domain-contracts-p02-01)
documents usage and remaining integration work.

Red verification failed collection because the new contracts were absent.
Round-trip checks then caught and corrected non-initializable discriminator
fields and a domain/subclass equality mismatch; schema checks caught missing
nested extra-field declarations. All 21 new
[contract tests](backend/tests/unit/test_domain_contracts.py) passed.
`make check` from `backend/` passed Ruff lint/formatting (37 files), strict mypy
(27 runtime files), and 62 tests with five explicit database/model-fixture skips
in 3.00 seconds. The first full run encountered existing local HTTP/subprocess
sandbox failures and was interrupted; its automatically approved run outside
the process sandbox passed. The source secret scanner reported zero findings
across 79 files; documentation checks and `git diff --check` passed. No provider
calls, model downloads or database connections occurred. Persistence, migrations,
authoritative ingredient checks, trend freshness, graph/SSE integration and
frontend contract generation remain later tasks. Existing
source-mapping/publication/media blockers remain.

P02-02 verified on 2026-10-03 with Python 3.12.14, PostgreSQL 16.14 and
pgvector 0.8.6. [Catalog mappings](backend/src/food_recommender/infrastructure/catalog.py)
define restaurant/recipe/review tables with explicit string primary keys,
separate type namespaces, unique logical-source/record pairs and a restrictive
review-to-restaurant foreign key. Names and source IDs must be nonblank; database
checks bound ratings, price bands, servings and coordinates. Raw cuisine/location
and recipe time strings are retained alongside nullable normalized filters.
Unavailable ingredients/allergens, nutrition, difficulty, availability, vibe and
coordinates retain SQL `NULL`; arrays preserve known empty values separately.
Synthetic review profile IDs are retained; profile ownership/FKs await P02-06.

[Alembic configuration](backend/alembic.ini), the
[migration environment](backend/migrations/env.py), revision template and
[initial catalog migration](backend/migrations/versions/0001_catalog.py) support
explicit PostgreSQL upgrades, offline SQL previews and dependency-ordered
downgrades. Imports/startup perform no migration or connection. Ruff targets now
include migration Python files. [Backend](backend/README.md#catalog-persistence-and-migrations-p02-02),
[developer](infra/development.md#migration-ingestion-and-release-availability) and
[CI](infra/ci.md) guides document the runnable commands and remaining scope.

Red verification failed collection because the catalog mappings were absent.
All 34 new tests passed: 30
[real PostgreSQL catalog contracts](backend/tests/integration/test_catalog_models.py)
and four [offline migration contracts](backend/tests/unit/test_catalog_migrations.py).
Verification used a disposable container with synthetic credentials, the pinned
PostgreSQL/pgvector image, a limited application role and no project volumes.
Tests verify fresh upgrade/downgrade/re-upgrade, schema parity, duplicate rejection,
foreign keys on insert/update/delete, SQL nulls and value/collection roundtrips;
per-test migrations/writes roll back. Explicit `alembic upgrade head` and
`alembic downgrade base` succeeded; `alembic check` found no new operations.
The disposable test container was removed afterward. `make check` passed Ruff lint/formatting
(42 files), strict mypy (28 runtime files) and all 101 tests with zero skips in
10.20 seconds, using existing seeded CPU model fixtures and fake Groq/Tavily
boundaries. Docker/test loopback access required automatically approved sandbox
escalation. No owner configuration, application database, provider calls or model
downloads were used. The source secret scanner reported zero findings across
84 files; documentation checks validated 115 local links, balanced fences and
unique checklist IDs, and `git diff --check` passed. P02-03 onward and the Phase 2
exit gate remain open.

P02-03 verified on 2026-10-03 with Python 3.12.14, PostgreSQL 16.14 and
pgvector 0.8.6. [Provenance mappings](backend/src/food_recommender/infrastructure/provenance.py)
add source artifacts, raw source records, documents and catalog media. Physical
file/URL/admin revisions retain logical dataset IDs, original locators, SHA-256
hashes, timezone-aware creation/retrieval timestamps and nullable publication
dates. Records preserve raw JSON and/or verbatim text, ingestion versions and
source/imported/generated attribution. Generated content requires a generator
identity and input hash; unavailable generator revisions remain null. Base and
augmented artifacts can link to the same canonical entity without duplication;
unresolved records retain null entity links. Type checks and catalog foreign keys
reject invalid associations. Documents retain optional chunk offsets; media
retain original filenames/URLs, private storage basenames, MIME types, sizes and
dimensions. Composite foreign keys reject document/image links across source
records; parent deletion/ID changes are restrictive.

[Revision 0002](backend/migrations/versions/0002_provenance.py) adds four tables
without changing existing catalog rows; its downgrade removes only provenance.
The migration environment registers the complete metadata without startup I/O.
[Backend](backend/README.md#source-document-and-media-provenance-p02-03),
[developer](infra/development.md#migration-ingestion-and-release-availability) and
[CI](infra/ci.md) guides document identities, attribution, migration commands and
remaining scope. Hash computation, source/entity reconciliation, document
construction/chunking, media decoding/storage, session ownership and cleanup
remain their later tasks; schema metadata alone does not verify image content
or dietary compliance.

Red verification failed collection because provenance mappings were absent.
The first migration run caught an unqualified JSONB type emitted by Alembic;
it was corrected before successful verification. All 52 new contracts passed:
50 [real PostgreSQL provenance tests](backend/tests/integration/test_provenance_models.py)
and two additional [offline migration previews](backend/tests/unit/test_catalog_migrations.py).
They verify raw-data/attribution/date/hash roundtrips, source revisions, unresolved
records, type namespaces, duplicate rejection, foreign keys, malformed metadata,
cross-record image rejection, partial-write rollback and catalog-preserving
upgrade/downgrade/re-upgrade. Catalog/provenance tests share a
[transaction-isolated fixture](backend/tests/integration/conftest.py).
`make check` passed Ruff lint/format (46 files), strict mypy (29 runtime files),
and all 153 tests with zero skips in 14.85 seconds, including existing seeded
CPU model fixtures and fake provider boundaries. Explicit Alembic upgrade/current,
schema check and downgrade succeeded on a disposable pinned PostgreSQL/pgvector
container with synthetic credentials and a limited application role;
`alembic check` found no new operations. The container was removed afterward.
Process/cache/Docker/loopback access required automatically approved sandbox
escalation. The source scan reported zero findings across 88 files; documentation
link/fence/checklist checks and `git diff --check` passed. No owner configuration,
application database, provider calls, model downloads or dependency changes
were used. P02-04 onward and the Phase 2 exit gate remain open.

P02-04 verified on 2026-10-03: revision `0003_embeddings` enables pgvector
and creates separate normalized text/image tables with model, revision, dimension,
input hash, timestamps and cascading document/media foreign keys. Nine new real
PostgreSQL tests cover exact cosine ordering, roundtrips, dimensions, duplicate
model/revision identities, invalid metadata, norms and parent cleanup. The scoped
catalog/provenance/vector/migration suite passed all 95 tests; strict mypy passed
30 source files and Ruff lint/format passed. Migration downgrade deliberately
retains the shared vector extension. No inference or model downloads occurred.

P02-05 verified on 2026-10-03: revision `0004_search` adds a stored English
`tsvector` derived from document text, a GIN lexical index and ordinary cuisine,
location/price, scoped-review and provenance-link indexes. Two new database
contracts verify stemming and automatic refresh after text updates, index
definitions and absence of HNSW/IVFFlat. All 32 scoped search/catalog tests passed;
strict mypy and Ruff lint/format passed. Exact vector search remains the baseline;
query planning, document construction and retrieval are still Phase 4 tasks.

P02-06 verified on 2026-10-03: revision `0005_context` adds hashed-token
browser sessions, UUID conversations/messages, conversation profiles, demo-profile
foreign keys (backfilled from existing reviews), owner-scoped upload associations
and dated trend cache/evidence. Composite foreign keys prevent cross-session
media links. Trend dates remain nullable; five-result bounds and a maximum 24-hour
cache lifetime are database enforced. Bootstrap creates an isolated checkpoint
schema owned by the limited role; the explicit `scripts/setup_checkpoints.py`
uses `AsyncPostgresSaver.setup()` without copying its tables into Alembic.
Six new database/checkpoint contracts pass, including setup twice, actual graph
checkpoint roundtrips across reopened connections and distinct UUID threads.
The context/catalog/provenance suite passed 86 tests; mypy and Ruff passed.
Trend freshness/query privacy, graph scheduling and HTTP cookie handling remain
their later phases. Session cleanup is P02-09.

P02-07 verified on 2026-10-03: framework-independent prepared catalog
snapshots and repository/unit-of-work ports now have async SQLAlchemy adapters.
Revision `0006_versions` adds positive optimistic versions to all catalog tables.
Catalog service transactions atomically write canonical rows, immutable source/raw
provenance, documents/media and both vector modalities. Replacements check
expected versions, preserve identities/raw revisions and replace retrieval rows;
deletes retain raw provenance as unresolved. Default exit, exceptions and
uncommitted success roll back. Database failures map to stable application codes.
Session-scoped conversation/profile/message/media operations and expiry-aware
trend-cache adapters share the transaction boundary. Backend composition wires
a lazy engine/session factory and FastAPI shutdown disposes the pool.
Four real repository tests and seven prepared-input tests passed; the scoped
repository/catalog/lifecycle suite passed 48 tests. Ruff and strict mypy passed.
File cleanup is completed in P02-09; HTTP CRUD and retrieval/ingestion remain
later phases. No paid providers were called.

P02-08 verified on 2026-10-03: eleven additional real PostgreSQL acceptance
tests cover duplicate canonical/source IDs through application adapters, complete
rollback of failed replacements, cancellation rollback, foreign-key rejection
without partial retrieval cleanup, legacy-review profile backfill, positive
versions, retained explicit restrictions and unauthorized message/media writes.
A two-connection race proves one winner and one conflict for the same expected
version. Cache tests prove inclusive retrieval/exclusive expiry boundaries,
unknown publication-date preservation and atomic failed refresh rollback.
Explicit `alembic upgrade head`, `alembic check` (no new operations) and supported
checkpoint setup passed on the limited disposable test role. Full backend
verification and conversation deletion evidence follow in P02-09.

P02-09 and the Phase 2 exit gate verified on 2026-10-03. Conversation deletion
locks and authorizes the owner, deletes messages/profile/media links, and invokes
LangGraph's supported `adelete_thread()` on the same psycopg connection and
transaction. All checkpoint namespaces, blobs and pending writes are removed
atomically; checkpoint failure or later transaction failure preserves everything.
Uploads shared by another conversation remain. Unshared uploads and their vectors
are deleted with durable cleanup jobs in revision `0007_cleanup`; catalog rows,
raw provenance, shared catalog media and other sessions remain untouched.

Post-commit cleanup uses validated basenames and descriptor-relative unlink,
never follows a symlink target, checks remaining media references and retains
failed jobs for explicit retry. Backend composition wires catalog/conversation
services and cleanup. `scripts/cleanup_media.py` processes up to 100 committed
jobs per call without provider credentials. Conversation deletion reports
`cleanup_pending` when cleanup needs retry. Active graph-run exclusion/cancellation
and the HTTP delete endpoint remain P07-11/P08-01; no graph runner exists yet.

Six new real database/filesystem/checkpoint tests verify erasure, rollback,
ownership, shared-upload lifetime, failure/retry, catalog preservation and actual
committed deletion after closing/reopening the pool. Ten filesystem unit tests
cover path traversal, invalid roots, missing-file retries and root symlinks.
The scoped deletion/catalog/repository/filesystem suite passed 49 tests before
the final committed-deletion case. Final `make check` passed Ruff lint/format
(70 files), strict mypy (38 runtime files) and all 208 tests with zero skips in
14.45 seconds, including existing local CPU fixtures and fake provider boundaries.
`alembic upgrade head`, explicit downgrade-to-base/re-upgrade, offline SQL
preview and `alembic check` passed with no new operations. Supported checkpoint
setup and the empty cleanup CLI passed. Documentation checks validated 187 local
links, balanced fences, 134 unique checklist IDs and the instruction-size budget;
`git diff --check` passed. The redacting scan reported zero findings across
112 source files. Verification used PostgreSQL 16.14 and pgvector 0.8.6
in a disposable pinned container with synthetic credentials and a limited role.
The first deletion run exposed a fixture teardown lock; the test was interrupted,
the teardown released its outer transaction before opening cleanup connections,
and subsequent scoped/full runs passed. Existing course/data/media artifacts,
owner configuration and original source/publication blockers were preserved.
The disposable test container was removed after verification.
No paid-provider calls, model downloads or dependency changes occurred.

## Phase 3 — Validated ingestion and media preparation

**Prerequisites:** Phase 2; reconciled data and recovered imagery from Phase 0 for full acceptance.

**Outputs:** resumable ingestion CLI, canonical seed catalog, source reports and media manifest.

**Verification:** import all baseline inputs, rerun unchanged imports and inject malformed/partial inputs.

- [x] P03-01 Implement source adapters that preserve raw attributes and map legacy IDs, cuisine/location fields and recipe time strings into canonical records.
- [x] P03-02 Merge base and augmented recipe/review records by identity; verify that enrichment does not create duplicate entities or overwrite authoritative fields silently.
- [x] P03-03 Parse legacy string-encoded image lists safely, validate element types and reject malformed or oversized values with source-specific errors.
- [x] P03-04 Implement source mappings for raw restaurant paragraphs and stable IDs for accepted additions; report unresolved records without breaking existing review relationships.
- [x] P03-05 Add Groq-backed structured extraction with Pydantic validation, no more than two repair attempts, quarantine on failure and administrator preview output.
- [x] P03-06 Reuse supplied captions with provenance; add separate vision inference for new images and avoid unnecessary recaptioning.
- [ ] P03-07 Implement image download validation, private-address/redirect restrictions, safe ZIP extraction, decoding, generated storage paths and ID-based recipe associations.
- [ ] P03-08 Add content-hash upserts, manifests and resumable progress; report imported/unchanged/rejected/unresolved totals and avoid destructive index resets.
- [ ] P03-09 Test empty/corrupt archives, missing/duplicate images, unsafe paths, absent captions, interrupted imports, malformed JSON and repeated runs.
- [ ] P03-10 Import and reconcile the complete seed corpus; record final counts and changes from the original 204/109/10 baseline.

**Exit criterion:** accepted records and available media are traceable, imports are idempotent/resumable, and every rejected or unresolved source item is reported.

**Evidence / blockers:**

P03-01 verified on 2026-10-03: Legacy source adapters preserve raw payloads and separate ID namespaces, normalize cuisine/location, retain unknown metadata, parse recipe durations to ISO minutes, and validate review links/dates. Seven adapter tests, Ruff and strict mypy passed.

P03-02 verified on 2026-10-03: Identity joins retain both raw source payloads and reject duplicate IDs, orphan enrichments and authoritative-field conflicts. Six merge tests, Ruff and strict mypy passed; absent enrichment preserves base records.

P03-03 verified on 2026-10-03: Bounded AST/literal parsing validates at most 20 distinct nonempty string references and rejects malformed, nested, executable-looking and oversized inputs with source/record errors. Twelve tests, Ruff and strict mypy passed.

P03-04 verified on 2026-10-03: Hash-bound paragraph mappings account for every raw paragraph and validate all legacy IDs; accepted additions receive deterministic UUIDs without renumbering existing restaurants. Six reconciliation tests cover stale/incomplete mappings and stable acceptance; Ruff and strict mypy passed. Six additions and 16 duplicate-name groups remain for P03-10 source review.

P03-05 verified on 2026-10-03: Groq structured generation uses the configured model, a three-call concurrency boundary and 30-second calls, with Pydantic/domain validation, at most two schema repairs, source-referenced quarantine and non-persisting preview results. Four offline extraction/provider-contract tests, Ruff and mypy passed. Groq structured-output/vision documentation was rechecked; no live inference was enabled.

P03-06 verified on 2026-10-03: Supplied captions retain imported attribution and report absent-caption references. New-image vision uses a separately injected model, decoded metadata-stripped images, bounded validation repairs, generated provenance and a content/model/version cache. Three offline tests, Ruff and mypy passed; cached/supplied captions invoke no provider.

## Phase 4 — Multi-source text retrieval baseline

**Prerequisites:** Phases 2–3.

**Outputs:** real restaurant/recipe/review retrievers, lexical/dense fusion and evidence contracts.

**Verification:** deterministic fixtures and labeled source-backed queries against PostgreSQL.

- [ ] P04-01 Construct retrieval documents containing restaurant descriptions, ambiance, signatures and shortcomings; recipe ingredients/directions/captions; and scoped review evidence.
- [ ] P04-02 Implement token-aware chunking and provenance offsets; preserve complete canonical ingredients for dietary checks even when retrieval uses excerpts.
- [ ] P04-03 Generate normalized MiniLM 384-dimensional embeddings on CPU with hashes, revision checks and batched upserts.
- [ ] P04-04 Implement parameterized PostgreSQL full-text and exact cosine search with applicable metadata filters and validated result limits.
- [ ] P04-05 Implement explicit hard-constraint handling and supported/conflicting/unknown evidence states; never classify missing dietary evidence as compliant.
- [ ] P04-06 Add restaurant/recipe/review source routing, reciprocal rank fusion with `k=60`, entity-level deduplication and up to 20 candidates per requested category.
- [ ] P04-07 Return typed evidence, original scores, source IDs and explicit no-result versus dependency-error outcomes.
- [ ] P04-08 Test exact filters, names, null metadata, IDs, empty/one-result queries, duplicate chunks, incompatible embedding dimensions/revisions and scoped reviews.
- [ ] P04-09 Create initial labeled text queries and record retrieval metrics before agent reasoning or later ranking changes.

**Exit criterion:** real PostgreSQL retrieval returns reproducible, constrained, cited candidates; no simulated LLM-generated search results remain in the new runtime.

**Evidence / blockers:** _Pending._

## Phase 5 — Multimodal retrieval and fusion

**Prerequisites:** Phase 4 and validated image corpus from Phases 0/3.

**Outputs:** CLIP image index, image queries, entity-level late fusion and evaluation comparisons.

**Verification:** image-to-image/text-to-image fixtures, missing-modality cases and weight experiments.

- [ ] P05-01 Generate normalized 512-dimensional CLIP image embeddings with verified model identity and actual entity/media links.
- [ ] P05-02 Implement CLIP text-to-image and image-to-image search using the matching model/revision; reject unsupported or mismatched inputs.
- [ ] P05-03 Resolve query images through authorized media IDs rather than caller-supplied paths or arbitrary URLs.
- [ ] P05-04 Add normalized text/image late fusion, initially `0.6/0.4`, and aggregate maximum evidence per entity/modality while retaining component scores.
- [ ] P05-05 Implement deterministic ties, empty/equal score handling, duplicate image protection and weight renormalization when an entire modality is unavailable.
- [ ] P05-06 Rank restaurants and recipes separately and prove that unrelated recipe imagery is never attributed to restaurant menu items.
- [ ] P05-07 Test expected image/recipe associations, partial imagery, malformed uploads, exact filters, image-only queries and text-plus-image queries.
- [ ] P05-08 Compare text-only, balanced, text-heavy and image-heavy results on labeled queries; record relevance/diversity and latency tradeoffs.

**Exit criterion:** text and image queries work with correctly associated real media, constraints remain intact, and fusion behavior is measured and explainable.

**Evidence / blockers:** _Pending._

## Phase 6 — MCP services and live food trends

**Prerequisites:** Phase 5 and provider/configuration ports from Phase 1.

**Outputs:** FastMCP server/client, typed read-only tools/resources, bounded Tavily search and cache.

**Verification:** protocol tests on both transports, fake-provider failure tests and explicit live search smoke test.

- [ ] P06-01 Implement `get_restaurant_info`, `recommend_by_vibe` and `get_review` using shared application services with explicit ambiguity/no-match results.
- [ ] P06-02 Add `search_restaurants`, `search_recipes` and `search_images` with constrained schemas, bounded limits and evidence-rich results.
- [ ] P06-03 Expose culinary-map, dataset-manifest and source-provenance resources without exposing arbitrary files or private session content.
- [ ] P06-04 Implement Streamable HTTP for Compose, stdio for local demos, connection lifecycle management and stderr logging for stdio.
- [ ] P06-05 Discover tool schemas at runtime, apply per-agent allowlists and validate arguments/results; reject arbitrary tool/server selection.
- [ ] P06-06 Add `search_food_trends` backed by Tavily with two searches/run, five results/search, a 90-day window and a 24-hour cache TTL.
- [ ] P06-07 Store URLs, excerpts, available publication dates and retrieval times; sanitize search queries to avoid sending private profiles/reviews/restrictions.
- [ ] P06-08 Enforce freshness at cache read and citation time; unknown publication dates cannot substantiate current trends.
- [ ] P06-09 Handle timeout, rate limits, no results, stale cache and missing credentials as explicit unavailable trend evidence.
- [ ] P06-10 Test tool/resource discovery, protocol errors, connection reuse, limits, path/SQL/tool injection, both transports and prohibited mutation capabilities.
- [ ] P06-11 Verify that Groq inference stays in the application, no sampling callback is required, and filesystem restrictions do not depend on roots alone.
- [ ] P06-12 Run an explicitly enabled Tavily smoke test with a fresh key and record dated evidence plus request usage; keep offline tests independent of it.

**Exit criterion:** the app can discover and call real retrieval/trend tools through MCP, and both live and unavailable-trend behavior are demonstrated.

**Evidence / blockers:** _Pending._

## Phase 7 — Six-agent hybrid LangGraph workflow

**Prerequisites:** Phases 4–6, shared typed contracts and PostgreSQL checkpoints.

**Outputs:** six real graph agents, persisted conversational state, bounded retrieval refinement and validated synthesis.

**Verification:** deterministic graph/provider tests and explicitly enabled end-to-end Groq smoke test.

- [ ] P07-01 Implement a configurable Groq adapter for structured outputs and tool selection as separate calls; validate text/vision capabilities with fresh credentials in opt-in setup.
- [ ] P07-02 Implement the User Profile Generator for restaurant/recipe/both intent, explicit and inferred preferences, optional scoped demo reviews and clarification.
- [ ] P07-03 Preserve restrictions across follow-ups, apply explicit corrections, and handle contradictory statements without silently resetting the profile.
- [ ] P07-04 Implement the RAG Retriever's source plan, evidence sufficiency checks and at most two refinements after initial retrieval; preserve hard constraints.
- [ ] P07-05 Implement the Food Trend Analyst with dated MCP evidence, candidate associations and explicit unavailable outcomes.
- [ ] P07-06 Implement the Food Style Expert for all candidates with supported cuisine/flavor/preparation assessments and unavailable-analysis behavior.
- [ ] P07-07 Implement the Nutrition Expert with deterministic ingredient checks, supported/conflicting/unknown assessments and strict exclusion behavior.
- [ ] P07-08 Implement the Recommendation Expert for up to five results/category, all expert outcomes, explanations and validated candidate/source references.
- [ ] P07-09 Wire a real `StateGraph`: sequential profile/retrieval, asynchronous fan-out, explicit all-branches join and exactly one synthesis invocation.
- [ ] P07-10 Return partial state updates, isolate branch output keys and reset transient analysis between turns; avoid shared mutable state and first-five truncation.
- [ ] P07-11 Add PostgreSQL thread checkpoints, UUID run/conversation IDs, one active run/conversation, session isolation and explicit cancellation handling.
- [ ] P07-12 Enforce timeouts, concurrency, transport/schema retry limits and the run deadline; record stage latency, usage and exhaustion without leaking prompts or keys.
- [ ] P07-13 Test actual branch overlap, join completion, branch failures, invalid JSON, unknown IDs/citations, insufficient results, checkpoint continuity and conflicting concurrent turns.
- [ ] P07-14 Run an opt-in full graph smoke test through real MCP/pgvector/Groq/Tavily with a known seed query; record outcome, limits and usage.

**Exit criterion:** all six roles operate on real retrieved data, synthesis waits for branch outcomes, follow-ups persist correctly, and failures cannot fabricate compliant results.

**Evidence / blockers:** _Pending._

## Phase 8 — FastAPI contracts and application behavior

**Prerequisites:** Phase 7 plus repository/media services.

**Outputs:** versioned API, SSE, catalog administration, media/session ownership and generated API schema.

**Verification:** HTTP integration tests with real database and fake provider boundaries.

- [ ] P08-01 Implement `/api/v1` conversation creation, history and deletion with browser-session ownership and conversation-data cleanup.
- [ ] P08-02 Implement message submission with text/preferences/media IDs and typed SSE progress, clarification, recommendations, error and terminal done events.
- [ ] P08-03 Add heartbeats, buffering controls and client-disconnect cancellation; commit completed responses before final events and prevent automatic POST replay.
- [ ] P08-04 Implement paginated restaurant/recipe browse and detail endpoints with validated filters and source-backed fields.
- [ ] P08-05 Implement authorized media upload/read with 10 MiB/20-megapixel limits, JPEG/PNG/WebP decoding, generated filenames and metadata stripping.
- [ ] P08-06 Implement local administrator login/logout, hashed password verification, HttpOnly SameSite cookies, expiry, CSRF/origin checks and limited access.
- [ ] P08-07 Implement extraction previews and explicit catalog create/update/delete operations; validate IDs, versions and delete intent on the server.
- [ ] P08-08 Prepare embeddings before final writes, atomically commit catalog/retrieval changes, and return conflicts without partially changing data.
- [ ] P08-09 Implement liveness/readiness and structured errors; keep stack traces and paid provider calls out of health responses.
- [ ] P08-10 Generate frontend TypeScript contracts from OpenAPI and add a check for schema/type drift.
- [ ] P08-11 Test HTTP/SSE contracts, pre/post-stream errors, session isolation, cancellation, retries by clients, invalid uploads, auth/CSRF and CRUD failure atomicity.

**Exit criterion:** the typed API supports the full recommendation/admin flow safely, updates retrieval data consistently, and has a verified frontend contract.

**Evidence / blockers:** _Pending._

## Phase 9 — Next.js frontend and administration

**Prerequisites:** Phase 8 and frontend scaffold.

**Outputs:** responsive chat/catalog/admin experience with accessible states and source-backed recommendations.

**Verification:** component tests and browser journeys on desktop/mobile viewport sizes.

- [ ] P09-01 Build App Router layouts/navigation and shared Tailwind/shadcn components with keyboard navigation, focus management and accessible labels.
- [ ] P09-02 Add the same-origin API proxy and generated-type client; keep database/provider credentials on the server and preserve SSE streaming.
- [ ] P09-03 Implement conversations/history/reset, text input, example prompts, clarification and follow-up messages.
- [ ] P09-04 Add editable preference controls distinguishing hard dietary constraints from soft preferences without silently clearing prior restrictions.
- [ ] P09-05 Implement image upload/preview/removal using media IDs, client-side guidance and server validation errors.
- [ ] P09-06 Show meaningful progress and cancellation; handle disconnected streams by loading conversation state rather than replaying inference.
- [ ] P09-07 Render restaurant/recipe cards, images, explanations, source excerpts/dates and explicit unknown/degraded states using sanitized content.
- [ ] P09-08 Provide catalog browse/detail views and label the synthetic course data accurately; avoid unsupported live availability or nutrition claims.
- [ ] P09-09 Add local admin sign-in, extraction preview, create/edit forms, version-conflict handling and confirmed deletion.
- [ ] P09-10 Test pending, empty, error, trend-unavailable and partial-image states plus mobile layout and keyboard-only journeys.
- [ ] P09-11 Run Playwright journeys for text/image recommendations, retained preferences, citations and CRUD; verify changes become searchable.

**Exit criterion:** a nontechnical user can request/refine recommendations and an administrator can maintain the catalog without mock results or placeholder writes.

**Evidence / blockers:** _Pending._

## Phase 10 — Evaluation, reliability, and hardening

**Prerequisites:** Phases 0–9, including a representative full dataset.

**Outputs:** versioned evaluation set/reports, tested guardrails and measured limitations.

**Verification:** automated acceptance suite, labeled retrieval evaluation and recorded local performance runs.

- [ ] P10-01 Build source-backed evaluation fixtures for the four PDF personas: health-conscious, adventurous, budget-conscious and family with allergies.
- [ ] P10-02 Add text/image queries, follow-up corrections, restrictive/no-match cases, missing dietary evidence, and expected abstention/clarification outcomes.
- [ ] P10-03 Label relevant entity IDs and supporting source evidence; record dataset, model, prompt and embedding revisions with reports.
- [ ] P10-04 Measure Recall@20, nDCG@5 and diversity; compare text, multimodal and fusion settings against the initial baseline before selecting tuned defaults.
- [ ] P10-05 Require zero fabricated recommendation/citation IDs and zero hard-constraint violations in deterministic acceptance fixtures.
- [ ] P10-06 Verify no allergen guarantees, invented nutrient quantities, unverified restaurant facts or unsupported current-trend claims appear in results.
- [ ] P10-07 Test prompt injection in reviews, captions, web excerpts and MCP responses; prove it cannot enable new tools, expose secrets or mutate the catalog.
- [ ] P10-08 Test 429/Retry-After, malformed schema output, missing credentials, model capability mismatch, database/MCP downtime and stale/unavailable trend evidence.
- [ ] P10-09 Test request deadlines, provider concurrency, cancellation, concurrent conversations, per-conversation run exclusion and checkpoint isolation.
- [ ] P10-10 Recheck upload/archive/network restrictions, admin/session/CSRF behavior, sanitized rendering and redacted logs; scan source and built assets for secrets.
- [ ] P10-11 Measure stage/end-to-end latency, local embedding resource use, token usage and search calls; report machine details and cold/warm behavior.
- [ ] P10-12 Run all offline unit/integration/contract/browser checks and explicit live smoke tests separately; record every skipped or blocked check honestly.

**Exit criterion:** acceptance fixtures satisfy grounding/constraint invariants, required failure cases pass, and quality/performance results are reproducible without unsupported claims.

**Evidence / blockers:** _Pending._

## Phase 11 — Local release and demonstration

**Prerequisites:** all v1 gates from Phases 0–10 satisfied; no hidden credential/media/live-integration blocker.

**Outputs:** reproducible local release, operational notes, demonstration evidence and limitations.

**Verification:** clean-checkout rehearsal, restore test and complete user/admin demonstrations.

- [ ] P11-01 Rehearse setup from a clean checkout with documented fresh credentials, pinned dependencies, model downloads, media recovery and Compose startup.
- [ ] P11-02 Verify database migrations, idempotent seed ingestion, readiness behavior and persistence across service restarts.
- [ ] P11-03 Back up and restore PostgreSQL plus media; verify catalog links, vectors and conversation/checkpoint behavior after restore.
- [ ] P11-04 Demonstrate real text and image retrieval, all six agents, live dated trends, citations and conversational refinements.
- [ ] P11-05 Demonstrate administrator preview/create/edit/delete with atomic searchable updates and cancellation/conflict/error handling.
- [ ] P11-06 Capture sanitized screenshots/demo steps for the portfolio; map course screenshot requirements separately where still relevant without claiming replacement-stack screenshots meet course grading rules.
- [ ] P11-07 Publish local setup/troubleshooting instructions and measured limits: synthetic catalog, sparse histories, unknown dietary evidence, provider requirements and unavailable capabilities.
- [ ] P11-08 Confirm the complete-release gate: validated imagery, real RAG, six-agent graph, live search integration, frontend/admin usability and passing acceptance tests.
- [ ] P11-09 Review all checklist marks and evidence with the user; preserve unresolved/deferred items and document the final tested versions.

**Exit criterion:** another developer can reproduce the full local application and its demonstrated behavior; degraded modes are documented, not used to conceal missing release requirements.

**Evidence / blockers:** _Pending._

## Deferred — Outside the first release

These are not requirements to check off for v1 and are not authorization to deploy or integrate external accounts.

- [ ] D-01 Plan public hosting, TLS, production secrets, deployment operations and provider spend controls before exposing the app publicly.
- [ ] D-02 Add multi-user authentication, authorization, private histories, retention/consent controls and account deletion.
- [ ] D-03 Add explicitly authorized social-media or other personal-history connectors with source provenance and privacy boundaries.
- [ ] D-04 Integrate a verified nutrition/allergen data source; distinguish measured nutrition from model-generated assessment.
- [ ] D-05 Benchmark HNSW/iterative filtered scans against exact retrieval on a larger labeled corpus before adopting approximate search.

## Documentation maintenance checks

Use these checks when changing the plan; they do not imply application completion.

- [ ] DOC-01 Keep all 35 baseline source artifacts represented in AGENTS.md and distinguish existing experiments from planned runtime behavior.
- [ ] DOC-02 Keep phase IDs, prerequisites, architecture defaults, interfaces and release gates aligned across both documents.
- [ ] DOC-03 Verify relative links/anchors, Markdown/code fences, unique checkbox IDs and the AGENTS.md instruction-size budget.
- [ ] DOC-04 Check that documentation contains no credentials and that provider/version claims link to official references.
- [ ] DOC-05 Preserve user-maintained progress and update evidence only for checks actually performed.
