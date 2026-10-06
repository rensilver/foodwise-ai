# Phase 11 — Local release verification

Recorded scope is P11-01 through P11-05. Use the
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


## P11-04 — Live text, image, six-agent and follow-up demonstration

Verified on 2026-10-06 in America/Recife. Use the
[executable live guide](../../infra/live-demo.md) and
[sanitized report](live_demo_report.json). The final report identifies base
revision `5cd1d5858067155c33e770cc815e787bf9ac7f60` and hashes the new verifier,
live probe and changed runtime files; every hash matches the final source.
OpenAI uses the configured `gpt-4o-mini`, without provider/model fallback.
Langfuse is disabled; keys are read from the original private configuration
only in the live probe and never copied into rehearsal files or printed.

A new random-port localhost PostgreSQL/pgvector container and private media
directory use generated database credentials and the limited application role.
Normal migrations/checkpoint setup, seed ingestion and pretrained CPU indexing
create 329 entities, 770 MiniLM text vectors and 118 CLIP image vectors. The
recovered recipe ZIP and nine approved-host review download cache files are
revalidated/reused; no owner database, checkpoints or vectors are copied.
The existing 16 entity-review issues remain explicit, with zero seed rejects.
All eight setup/live command stages return zero.

| Turn | Real behavior | Run seconds | OpenAI attempts | Tokens | Fresh searches |
| --- | --- | ---: | ---: | ---: | ---: |
| Restaurant text | Korean/Fullerton retrieval recommends The Iron Kettle, restaurant `1000088` | 15.176 | 7 | 8,132 | 1 |
| Image recipe follow-up | Owned Beef Bulgogi upload retrieves its actual recipe `20`, with text/image scores | 8.555 | 6 | 10,178 | 0 |
| Hard allergy follow-up | Retained Korean cuisine plus explicit soy allergy; zero suggestions after three retrieval attempts | 3.911 | 4 | 2,148 | 0 |

The two positive turns each execute all six real domain roles successfully.
Recorded timing spans verify profile then retrieval, simultaneous expert activity,
and a single synthesis after all three experts finish. Their final entity IDs
and nonempty catalog citation IDs belong to the retrieved candidate set.
Image search consumes an application-issued session-owned upload ID, with normal
bounded decoding/metadata removal and ownership checks, and finds the recipe
that owns the catalog image. MiniLM and CLIP scores come from actual exact
PostgreSQL/pgvector retrieval, rather than simulated candidates or stored-vector
self-queries. Retained Fullerton location does not filter the recipe query.

One fresh Tavily search returns eligible dated public evidence; the image turn
uses its eligible cache entry. Both positive turns select and publish supported
source quotations associated with their actual candidate. The cited
[Korean convenience-store report](https://nypost.com/2026/08/25/lifestyle/viral-korean-convenience-store-culture-comes-to-la)
has a provider-supplied date of 2026-08-25 and a current retrieval timestamp.
The application independently enforces the 90-day evidence window and 24-hour
cache lifetime. Tavily now receives explicit start/end dates and publication
filtering from its [documented API](https://docs.tavily.com/documentation/api-reference/endpoint/search).
Provider dates can reflect source updates; this is not an independent editorial
publication-date audit. The claims describe culinary interest and do not create
operating, menu, nutrition or availability facts for the catalog restaurant.

A new graph and runner are constructed on every turn. Only the real PostgreSQL
checkpoint supplies prior history/profile; read-back matches each completed
positive response. The image turn retains cuisine and changes category from
restaurant to recipe. The final explicit soy allergy remains hard/explicit in
the saved profile. Canonical soy-containing ingredients and unknown compliance
produce no eligible recipes; synthesis returns a completed, cited-entity-free
response with the evidence limitation. Trend analysis is unavailable for this
empty candidate set, as expected; no unsafe suggestions fill the empty result.

Earlier isolated rehearsals exposed genuine failures: paraphrased style/synthesis
quotes, malformed trend claims, stale/undated search results with the obsolete
`days` request field, an invented hard allergen named `none`, and a verifier error
on missing outcomes. Those failed projects were removed and never counted as
acceptance. The final change keeps all original dietary/citation/claim gates:
style and trend inference select eligible source options by index, followed by
application binding and grounding checks; synthesis gets revalidated style
quotations as guidance. Schema repairs include field locations/types without
input values. Domain repairs share the same repair allowance/deadline. Inferred
restriction additions require the named value in a current-message quote and
restriction language for hard additions; placeholders and negated allergy
additions are rejected. Explicit fields and prior hard restrictions retain their
existing authority. Fake-provider fixtures follow the internal selection schemas;
external expert/API contracts and dependency locks are unchanged.

The final measured run uses 17 OpenAI attempts, 20,458 reported provider tokens
and one fresh search. These totals cover the committed three-turn run, excluding
previous failed rehearsals and diagnostics; no monetary charge is estimated.
Cached model files/OS caches are reused, so this is not a cold-cache performance
benchmark. Each run retains the 120-second deadline, 30-second calls, three-call
process concurrency, two transient retries, two shared schema/domain repairs,
one synthesis repair, and at most two Tavily searches.

The final affected suite passes 184 offline tests in 10.79 seconds, including
complete candidate coverage, selection/schema/grounding repair and exhaustion,
restriction addition/removal/retention, injection, citations/unknown IDs, graph
ordering, leases/cancellation, Phase 10 fixtures and verifier failure handling.
Ruff lint/format (318 Python files including the verifier), strict mypy (173
runtime modules), OpenAPI consistency, Markdown links/fences/Bash syntax, task-ID
uniqueness, the root instruction budget, the redacting source scan and
`git diff --check` pass. Sandbox graph/process tests initially stalled and were
stopped; the final bounded offline run used approved local process access.
The Makefile's uv invocation encountered sandbox cache/DNS restrictions; the
installed locked environment ran the equivalent tools directly, without changing
locks or installing dependencies.

Cleanup deletes the synthetic conversation and supported saver checkpoints,
browser session and upload, then removes the disposable container/anonymous
PostgreSQL volume and generated media/cache copy. Existing container IDs, start
times and restart counts match the initial inventory. Owner configuration,
original media/datasets, model bundles and course artifacts are preserved.
Private redacted diagnostic/rehearsal logs remain ignored locally. This small
scripted demonstration verifies live integration, not representative relevance,
verified nutrition/allergen safety, browser screenshots or administrator CRUD.
P11-05 onward, complete-release, publication/entity-review and optional Cloud
operational gates remain separate.

## P11-05 — Administrator preview, searchable CRUD and recovery

Verified on 2026-10-06 in America/Recife against revision
`671c8292851da66430c89233d64b00ea84a6e30b` plus the report's hashed verifier,
fixture, runtime fix and tests. The [sanitized report](admin_demo_report.json)
records every executed stage, model revisions, versions, individual browser
outcomes and cleanup. Reproduce with the [administrator guide](../../infra/admin-demo.md).

Four production Chromium journeys pass through Next.js and its same-origin
proxy to real FastAPI, limited-role PostgreSQL 16.14/pgvector 0.8.6 and HTTP MCP.
The browser stage takes 67.833 seconds including fixture startup, production
build and teardown; individual journeys take 4.118–5.594 seconds. The fixture
seeds one original restaurant and recipe with its actual image, using pretrained
CPU MiniLM/CLIP. Extraction and structured inference are controlled, live trends
unavailable and external Python network connections blocked. No owner dotenv,
application database/media volume or provider credentials are read; no paid provider/Cloud call occurs.
This is a small-catalog administration demonstration, separate from full-corpus
and live-provider P11-01–04 evidence.

Both categories demonstrate extracted previews without persistence, explicit
preview discard, separate create, edit and confirmed deletion. Keep it and Escape
close named deletion dialogs without sending DELETE or changing rows. Invalid
recipe duration/oversized restaurant signature input produces a real typed 422
while preserving drafts and prior catalog/document/vector snapshots. Revoking
the server session produces authentication failure; sign-in preserves the draft
and the next explicit save commits version two. A separate authorized browser
creates a real optimistic version conflict; the original browser keeps its draft,
reviews version three and explicitly saves version four. Restaurant browsing
also verifies filters, pagination, details and return URLs.

Edited restaurant and recipe identities appear in validated recommendations
with both lexical and dense retrieval ranks through the actual API/graph/MCP
flow. After confirmed deletion, detail returns 404 and recommendations omit
the deleted identity. SQL inspection finds only the original one restaurant,
one recipe, two text vectors and one image vector before teardown; zero
administrator entities remain. Raw provenance is retained according to the
catalog contract. Temporary conversations created by the new journeys are
explicitly deleted, and the entire disposable database is removed afterward.

All 21 real database/API contracts pass with zero skips (12.084 seconds for
the command stage). They cover authorization, origin/CSRF, explicit delete
confirmation, versions, embedding dependency failure, late SQL uniqueness
failure/rollback and linked-review retrieval deletion. Five cancellation cases
cancel real asyncio tasks during preparation or after create/edit/delete SQL
mutation before commit. Complete row snapshots include timestamps, provenance,
documents, text/image vector values, media and cleanup jobs. Each cancelled task
propagates cancellation, restores the snapshot and permits a subsequent write.
These prove application-task cancellation. The administrator UI provides
preview discard and delete confirmation cancellation; an already committed
write is not undone by disconnecting, and there is no admin in-flight Stop UI.

The first browser error demonstration found invalid recipe durations escaping
as `ValueError` and returning HTTP 500. The application now maps this input
failure to `invalid_request`/422 before preparation or any write. Six real HTTP
regressions cover create/edit for preparation, cooking and total-time fields,
checking redaction and unchanged complete row snapshots. Browser error and
recovery demonstrations now pass. Earlier failed verifier attempts removed
their isolated resources and did not change the owner's services.

Additional checks pass: 22 offline preparation/package-boundary/verifier tests
(3.24 seconds), five verifier/backup-cleanup checks (0.69 seconds), all 25 frontend
unit/component tests (9.07 seconds), backend Ruff/format (319 files), strict mypy
(173 runtime files), OpenAPI/generated-contract drift, frontend format/lint/types,
Markdown links/fences/Bash syntax, task-ID uniqueness, source scan and
`git diff --check`. These are affected checks, not a new full-release acceptance
run. Versions include Python 3.12.14, Node 24.19.0, pnpm 12.8.1, Playwright 1.63.0,
FastAPI 0.142.2, SQLAlchemy 2.1.2 and psycopg 3.3.6; model IDs/revisions are in
the report. Dependency locks are unchanged.

The verifier removes its container/anonymous volume and private media/work
directory; original container identities, start times and restart counts match
the initial inventory. Owner configuration, datasets, recovered media, model
bundles and course artifacts are preserved. Private failure logs and synthetic
Playwright failure artifacts remain ignored. Only P11-05's completion mark
changes. P11-06 onward, portfolio/course screenshots, complete-release review,
publication/source/entity-review and optional Cloud gates remain separate.

## P11-06 — Sanitized portfolio and separate course screenshot map

Verified on 2026-10-06 in America/Recife against base revision
`f21589a13ab5a42ac98b1e89b471ac87191c03f0` plus the capture report's hashed
verifier and browser journey. The [seven-image gallery](portfolio.md),
[sanitized report](portfolio_report.json) and
[presenter/reproduction guide](../../infra/portfolio-demo.md) cover desktop
meal entry, text sources, a hard milk restriction/empty follow-up, owned image
retrieval on mobile, and administrator preview/create/edit/delete confirmation.

The opt-in `--portfolio-dir` mode reuses the isolated administrator harness.
One production Chromium journey passes in 8.365 seconds; its command stage
including build/startup takes 50.181 seconds. All 21 real database/API contracts
execute with zero failures/errors/skips (10.284 seconds). Real Next.js/FastAPI,
PostgreSQL 16.14/pgvector 0.8.6, HTTP MCP, CPU MiniLM/CLIP and persisted follow-ups
use one original restaurant/recipe and the actual recipe-1 image. Inference and
extraction are controlled; style/trends are unavailable and remain visible.
This captures the UI, not live-provider acceptance. The live six-agent/dated
trend demonstration remains the separate P11-04 evidence.

Seven PNGs totaling 1,813,762 bytes decode without metadata. The report records
each image's dimensions, byte size and SHA-256 digest; every image and script
hash matches. All final images are visually reviewed for privacy and complete
loading. A first capture exposed an image-loading race; the final journey waits
for every rendered image to finish decoding, and checks numeric image evidence
in the persisted mobile result. Each screenshot carries a harness-added label
identifying synthetic inputs, controlled inference and unavailable trends.
Only the seven allowlisted images are exported after successful verification
and cleanup. Password fields are masked, recognizable private text is rejected,
browser chrome is absent, and raw logs/traces/configuration/uploads stay out
of the export. A new destination is required to preserve previous captures.

The [course requirement map](course-screenshots.md) and
[PDF identity manifest](course_screenshot_map.json) are based on local text
extraction from all 12 supplied overview PDFs. Eleven require specific `.jpg`
filenames and code/output or terminal views on page one. PDF 12 lists full MCP
application deliverables without a screenshot filename. The map preserves exact
case/spelling, requested views, local PDF hashes and relevant current
implementation/evidence links. It does not infer an unprovided final rubric,
claim original-lab captures completed, or rename portfolio images to satisfy
course grading. Original PDFs/notebooks/media and historical outputs remain
unchanged and ignored.

Twenty offline verifier/package-boundary tests pass (5.08 seconds), including
incomplete/invalid PNG rejection and cleanup after a failed inventory prerequisite.
Ruff lint/format, frontend Prettier/ESLint/TypeScript, documentation links/fences/
Bash syntax, asset/source hashes, checklist task-ID uniqueness/instruction budget,
the redacting source scan and `git diff --check` pass. Listing the original
P11-05 selection still yields exactly its four administrator journeys; the new
capture is skipped in normal runs. Runtime behavior, locks and course artifacts
are unchanged.

The final receipt has only the original one restaurant, one recipe, two text
vectors and one image vector, with no administrator entities. Synthetic
conversations/uploads are deleted by the journey. The disposable database/volume
and private work/media directory are removed; original container identities,
start times and restart counts match. No owner dotenv, provider credential or
application database is read; no paid provider/Cloud call occurs. Only P11-06's
completion mark changes. P11-07 onward, complete-release, source/entity-review/
publication and optional Cloud gates remain separate.
