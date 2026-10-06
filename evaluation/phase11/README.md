# Phase 11 — Local release verification

Recorded scope is P11-01 through P11-03. Use the
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

## P11-03 — PostgreSQL and media backup/restore

Verified on 2026-10-05 in America/Recife. The
[sanitized report](backup_restore_report.json) records 46 successful command
stages against revision `c84c1d7268fb1ec28939bad1cd528efe1359ef41` plus the
SHA-256 identities of the verifier, media archive helper and container probes.
Those recorded script hashes match the final source files. Docker Engine
29.8.0/Compose 5.5.1 run PostgreSQL 16.14/pgvector 0.8.6. The
[backup/recovery guide](../../infra/backup-restore.md) contains executable
maintenance-window commands and the isolated reproduction command. Application
behavior, dependency locks and course artifacts are unchanged.

The verifier builds production images with separate source/target Compose
projects, localhost ports and independent randomly generated database/admin
credentials. It never reads the owner's dotenv. A fresh source imports 329
entities with zero rejects and the same 16 entity-review issues, then indexes
770 MiniLM text and 118 CLIP image vectors using the normal adapters. Pinned
model bundles, the recovered recipe ZIP and nine original review download
cache files are reused. OpenAI settings are synthetic, Tavily absent and
Langfuse disabled; no paid calls or model/media downloads occur.

An HTTP-owned synthetic conversation/upload is linked through the application
repository. One message, an explicit hard preference and a synthetic control
graph checkpoint are persisted through the real PostgreSQL saver. After
quiescing frontend/API/MCP and completing all one-off writers, the verifier
creates a 2,412,263-byte custom PostgreSQL dump and a 254,269,440-byte media tar.
The complete media volume contains 129 files/254,035,105 bytes: 118 catalog
images, one upload, the import manifest and nine original download files.
Backup hashes are recorded and checked; changing one archive byte is rejected
before target mutation. Raw archives are kept private and never committed.

The disposable source volumes are removed before the target starts. Target
bootstrap creates pgvector and the same limited `foodwise` role with new
passwords; its application/checkpoint table count is zero. `pg_restore` runs
with `--clean --if-exists --single-transaction --exit-on-error`. The complete
media archive restores into the empty new media volume. No migrations, seed
import, re-embedding or checkpoint setup is needed to rebuild recovered data.
`alembic check` then verifies model/migration parity.

All 25 table snapshots match exactly, including IDs, raw/provenance records,
timestamps, versions, full vector values, sessions, profiles, messages and
checkpoint blobs/writes. All 119 registered media hashes, byte sizes and image
decoding checks match, and the complete volume digest matches independently.
All 155 constraints remain validated; all application tables/sequences retain
`foodwise` ownership. The 109 recipe-image associations and nine review-image
associations with actual restaurants remain intact.

Real PostgreSQL search adapters return identical lexical/dense restaurant and
recipe results, scores and citation identities. Queries use stored compatible
vectors to exercise exact cosine retrieval without re-embedding; this is not
a new model-quality measurement. CLIP self-queries recover the actual recipe
and scoped review/restaurant image; another demo profile receives no review
image hits. All 109 browse recipe images serve and decode through their actual
entity routes before and after recovery, with catalog citations present. Review
imagery remains scoped retrieval evidence rather than browse thumbnails.

The retained browser cookie reads identical history and upload bytes after
restore; strangers receive 404 for both. A new probe process reads the saved
checkpoint and advances from turn one to turn two while preserving the hard
preference. Deleting that restored conversation through HTTP removes messages,
profile, media links, the unshared upload/file and all thread checkpoint rows;
catalog media and search results remain intact. Readiness and the Next.js
restaurant/recipe proxy return 200. This control graph verifies persistence;
live six-agent refinement remains P11-04.

Two earlier harness runs exposed verification assumptions: only 109 recipe
images are browse thumbnails, while nine review images use scoped retrieval;
Snap Docker requires pipe-backed stdin/stdout instead of regular redirected
descriptors. Both failed projects were cleaned up. The corrected runner pumps
binary archives through bounded subprocess pipes without retaining the entire
media archive in memory. A red/green regression verifies exact binary transfer,
pipe descriptors, private destination permissions and absence of archive bytes
in logs. The final committed report is the successful rerun.

The final targeted suite passes 29 tests in 6.34 seconds: archive round trips,
hidden files, traversal/link/special-file/duplicate/truncation/expansion rejection,
nonempty-target preservation, pair corruption/missing-file rejection, failure
cleanup, Docker binary transfer, package boundaries and health behavior. The
initial sandboxed health test stalled and was stopped; the bounded final run
used automatically approved local process access. Ruff lint/format checks pass.
Five Markdown files pass 134 local link/anchor checks and 16 Bash syntax blocks;
all 152 task IDs stay unique and `AGENTS.md` stays at 32,759 bytes. The redacting
source scan finds zero findings across 483 source/build files, and
`git diff --check` passes. Only P11-03's completion mark changes; all later tasks
and existing blockers are preserved.

Cleanup removes both projects' containers/networks/volumes, dedicated image
tags, raw backup pair/manifest and temporary credentials. Existing containers
retain their identities, start times and restart counts. Private redacted
rehearsal logs remain ignored locally. This task rehearses offline same-version
recovery, not online/PITR/cross-version or Cloud recovery; it creates no retained
backup of the owner's stack. P11-04 onward, complete-release/live acceptance,
optional Cloud operational gates and publication/source-review blockers remain
separate.
