# Phase 11 — Local release verification

Recorded scope is P11-01 and P11-02. Use the
[clean-checkout setup guide](../../infra/release-setup.md) for the executable
sequence. Other Phase 11 tasks and the complete-release gate remain separate.

## Checkout, credentials and recovery

The 2026-10-05 rehearsal uses `git archive` of revision
`2cf7116dc0625ece90c17b7f16876f558e94bb91` in an ignored, separate directory.
All 490 archived tracked files match that revision byte-for-byte. No existing
virtual environment, frontend installation, model bundle, generated media,
database, checkpoints or retrieval indexes was copied. Shared uv/download and
Docker layer caches may be reused; this is not an empty-cache benchmark.

Provider settings are explicitly synthetic for startup. Independently generated
database passwords and a new random administrator credential/Argon2id hash
exercise real local configuration. The guide documents owner-issued fresh
OpenAI/Tavily keys and a user-chosen administrator password. Account issuance,
rotation and paid provider capabilities are not tested here. No inference,
trend smoke or Cloud export is invoked; Langfuse is disabled. Existing
[Phase 10 live evidence](../phase10/README.md#p10-12--separate-offline-and-live-checks)
remains independent of this setup run.

Automatic approval review rejected a proposed copy of the owner's OpenAI key
into the rehearsal dotenv file because it would propagate a secret. That
operation never executed. The accepted rehearsal does not read/copy the owner's
dotenv or provider credentials. This does not leave a credential-copy operation
pending.

The owner-held recovered recipe archive was separately copied into the checkout:
215,139,852 bytes, SHA-256
`2dbc15a307070267c0eea1e45642f53a2e13182a9b797e1f6a027d5c3a5cb68b`.
Model provisioning downloads public, revision-pinned MiniLM and CLIP into empty
directories; ten MiniLM and eight CLIP files have verified manifest hashes.
Review media recovery uses the importer's approved-host download path, rather
than copying prior generated media. Course PDFs/notebooks remain local and
ignored; they are not runtime knowledge sources.

## Recorded results

The sanitized [setup report](clean_setup_report.json) records installed versions,
lockfile/model/archive hashes, stage results and HTTP checks. Its status and
individual checks define the verification outcome; no later acceptance task is
implied by a healthy startup.

The rehearsal passed. Locked host installs created 157 backend and 537 frontend
packages; `uv pip check`, offline lock validation, runtime imports and the
20-table ORM registry passed. Both production images built from that checkout.
Fresh database bootstrap, Alembic migrations and supported LangGraph checkpoint
setup passed. Import created 329 entities with zero rejects and 16 explicit
entity-review issues. Indexing created all 770 text and 118 image vectors;
all 109 recipe and nine newly downloaded review images are present.

All four serving containers became healthy, with zero OOM kills and zero
restarts at inspection. API readiness, direct catalog reads, frontend liveness,
product HTML and same-origin catalog proxy requests returned 200. A recipe
image served through Next.js returned PNG/200 and decoded at 1024 × 1024.
HTTP MCP discovery returned all seven culinary tools and three resources.
The actual database is PostgreSQL 16.14/pgvector 0.8.6, with a limited application
role. These are setup checks, not complete browser/live recommendation acceptance.

The rehearsal uses its own Compose project, separate image tags, newly created
database/media volumes and randomly assigned localhost frontend/backend ports.
Database and MCP ports remain private. The documented isolated override uses
the low-memory file plus 2,304 MiB for backend/setup and 1,536 MiB for MCP so
the old 512 MiB scaffold limit does not constrain one-off CLIP indexing. These
are ceilings, not peak measurements or proof of resident inference capacity.

At the close of P11-01, migration/idempotency/restart acceptance, backup/restore,
real six-agent/live recommendations, administrator journeys and complete-release review remained
P11-02 onward. Historical source/entity-review/publication blockers are preserved.

The disposable project containers, network, database/media volumes and dedicated
image tags were removed after recording results. Temporary dotenv credentials
were deleted; only ignored installation/model caches remain. The existing
`tasty-recipe-ai` backend/PostgreSQL containers remained healthy. The owner's
configuration, datasets and course artifacts were untouched.

Document verification passed for six changed Markdown files: 168 relative
links/anchors, balanced fences and 22 Bash blocks checked with `bash -n`.
All 152 task IDs remain unique; only P11-01's completion mark changed.
`AGENTS.md` remains within the 32 KiB instruction budget (32,759 bytes).
The redacting source scan found zero findings across 473 files, and
`git diff --check` passed. No application behavior changed, so unrelated
application/browser suites were not rerun; the fresh setup itself supplied the
integration evidence above.

## P11-02 — Migrations, idempotency, readiness and restarts

Verified on 2026-10-05. The [sanitized report](persistence_report.json) records
49 successful command stages against revision
`ec932fed6169a7713484f6c3ecb8746331596cf6` plus SHA-256 identities for the two
new verification scripts. Docker Engine 29.8.0/Compose 5.5.1 run PostgreSQL
16.14/pgvector 0.8.6 with the limited application role. Use the
[executable guide](../../infra/release-setup.md#migration-ingestion-and-restart-verification-p11-02)
to reproduce it. Application behavior and dependency locks are unchanged.

The verifier builds the current production services in an isolated project
with fresh database/media volumes, synthetic OpenAI settings, no Tavily key
and tracing disabled. It reuses pinned CPU model bundles, the separately
recovered recipe ZIP and nine cached approved-host review downloads. The normal
importer regenerates/validates media; no catalog, vectors or checkpoints are
copied from the owner's database. No paid provider calls or model/media
downloads occur.

All nine Alembic revisions upgrade a fresh database, downgrade the still-empty
database to base and upgrade again to `0009_admin`. `alembic check` reports no
model/migration differences. Supported LangGraph setup creates its four tables
and ten library migration records in `foodwise_checkpoints`. Repeating Alembic
upgrade and checkpoint setup preserves every row hash.

First import creates 210 restaurants, 109 recipes and ten reviews (329 entities),
with zero rejects and the existing 16 entity-review issues. Repeat import reports
329 unchanged, zero imports/rejects and the same unresolved issues. The database
retains 1,006 provenance documents; text indexing selects 770 documents and
creates 770 vectors. Image indexing creates 118 vectors for 109 recipe and nine
review images. Repeat indexing embeds nothing: 770 text and 118 image vectors
are unchanged. All table/media hashes match before and after repeat ingestion
and indexing, including IDs, versions, timestamps, provenance and vector values.

HTTP readiness returns 503 before application migrations, before checkpoint
setup and after empty-database downgrade. It returns 200 after initialization,
even with an empty catalog; readiness is a dependency check. Stopping MCP returns
503 with MCP unavailable; stopping PostgreSQL returns 503 with database/schema/MCP
unavailable. Both recover to 200. Liveness remains 200 throughout. Separate real
adapter probes mark a missing media root or MiniLM bundle unavailable while
the remaining dependencies pass.

After creating an owned conversation and image upload over HTTP, the probe
stores one synthetic message and an explicit hard preference through the
application repository. A synthetic control graph uses the real PostgreSQL
checkpoint saver. The verifier compares all 25 table hashes and 119 registered
media files (118 catalog images plus that upload) after `compose restart` and
after `compose down`/`up` with retained volumes. Every hash matches; all media
hashes, byte sizes and image decoding pass. Owned history/preferences and image
bytes survive; strangers receive 404. A new probe process reads the retained
checkpoint and advances from turn one to turn two with its restriction intact.
Next.js liveness and same-origin restaurant/recipe catalog reads also pass
after recreation. This control graph proves saver persistence; real six-agent
live follow-ups remain P11-04.

An initial harness run exposed reassignment of automatic localhost ports after
Docker restart; the verifier now resolves the backend address after each
recovery/restart. A subsequent run was interrupted to correct the distinction
between 1,006 stored provenance documents and 770 indexed text documents. Both
earlier disposable projects were cleaned up. The committed report is the final
successful rerun. A red/green offline regression also verifies that an initial
Docker-inventory failure removes temporary credentials and records failure.

The final targeted pytest run passes 19 health, package-boundary/cold ORM and
verifier cleanup tests in 7.96 seconds. The initial sandboxed HTTP test stalled
and was terminated; the bounded rerun used automatically approved local
process/network access. Ruff lint/format checks pass for both scripts and the
regression test. Four Markdown files pass 122 relative link/anchor checks and
13 Bash syntax blocks. All 152 task IDs remain unique; only P11-02's completion
mark changes. `AGENTS.md` remains 32,759 bytes. The redacting scan finds zero
findings across 477 source/build files, and `git diff --check` passes.

Cleanup removes the verifier's containers, network, volumes, dedicated image
tags and temporary credentials. Existing containers retain their identities,
start times and restart counts. Owner configuration, datasets and course
artifacts are preserved. P11-03 onward, live/full-release acceptance, optional
Cloud operational gates and publication/source-review blockers remain separate.
