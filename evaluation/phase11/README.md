# Phase 11 — Local setup rehearsal

Scope is P11-01. Use the [clean-checkout setup guide](../../infra/release-setup.md)
for the executable sequence. Other Phase 11 tasks and the complete-release gate
remain separate.

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

Migration/idempotency/restart acceptance, backup/restore, real six-agent/live
recommendations, administrator journeys and complete-release review remain
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
