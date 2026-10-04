# Phase 8 API acceptance evidence

Verified locally on 2026-10-04 on `feature/phase8-fastapi-contract`, with one
dedicated commit for each P08-01 through P08-12 task. The phase implements FastAPI
behavior and generated frontend contracts. Browser journeys and the same-origin
Next.js proxy remain Phase 9 work.

## Implemented and tested contracts

| Tasks | Evidence |
| --- | --- |
| P08-01 | Owned creation/history/deletion, checkpoint/profile cleanup, active-run deletion conflicts, completed-run deletion and shared-upload retention. |
| P08-02–03 | Validated message POST with explicit preferences/media IDs and replay UUID, all five SSE events, six-stage activity, heartbeats, buffering controls, completed-response persistence before delivery, deadline and disconnect cancellation. |
| P08-04–05 | Paginated category-specific filters, source-backed nullable detail fields, synthetic labels, owned JPEG/PNG/WebP uploads and reads, 10 MiB/20-megapixel bounds, chunked-body bounds, generated storage names, metadata stripping and animated/invalid-content rejection. |
| P08-06–07 | Real Argon2id verification, separate hashed admin sessions/CSRF values, cookie flags, expiry/revocation, origin enforcement, non-persisting extraction previews, server-generated IDs, partial updates, immutable source identity, optimistic versions and explicit deletion bodies. |
| P08-08 | Lossless bounded MiniLM preparation before transactions; catalog/document/vector atomicity, preparation/late-write rollback, preserved existing image vectors, stale-version conflicts and confirmed restaurant/review retrieval cleanup with retained raw provenance. |
| P08-09–10 | Typed health/error schemas, redacted pre/post-stream errors, local dependency readiness without paid calls/model loading, deterministic offline OpenAPI export and generated strict TypeScript contracts. Both drift checks reject deliberately altered artifacts. |
| P08-11–12 | Real PostgreSQL/pgvector and supported checkpoints through HTTP, six actual graph roles and real MCP retrieval with fake inference, follow-up restriction retention, replay/concurrency rejection, cancellation without history-driven resumption, explicit complete ORM registration/migration parity and import boundaries. |

The API integration tests are in
[backend/tests/integration](../../backend/tests/integration/); the full graph
HTTP journey and real ASGI disconnect are in
[test_api_workflow.py](../../backend/tests/integration/test_api_workflow.py).
Unit contracts check actual heartbeat timing and ASGI 2.4 disconnect handling in
[test_api_sse.py](../../backend/tests/unit/test_api_sse.py).
[Package contracts](../../backend/tests/contract/test_package_boundaries.py)
reject concrete I/O in handlers and adapter/provider imports into core modules.
The existing schema integrity tests compare the complete model registry with
upgraded migrations and exercise downgrades/rollbacks.

The final review added explicit restaurant/review cleanup while retaining the
ordinary catalog service's linked-review protection. It also found and fixed a
conversation deletion lock conflict: runs hold advisory and key-share locks;
deletion holds the same advisory lease without a row lock that would block its
own separate unit of work. The regression test deletes a completed conversation
within a bounded timeout and verifies its checkpoint has disappeared; active
turn deletion returns `409`.

## Verification results

Backend `make check` passed Ruff lint/format checks (265 files), strict mypy
(152 runtime files), deterministic OpenAPI drift verification and all **463
tests**, without skips. This includes the 26 focused API/SSE contracts, existing
real database/migration/retrieval/MCP suites and provisioned offline pretrained
MiniLM/CLIP checks. The targeted lease/deletion/checkpoint regression passed
seven tests after the lock correction.

Frontend `pnpm check` passed generated-type drift, ESLint, strict TypeScript,
one Vitest component test and all five Node configuration/build tests. The
configuration tests include an isolated production build and checks for private
values in browser artifacts. No Phase 9 browser journeys were implemented or
claimed. One-off negative drift checks altered only temporary/copied artifacts,
confirmed both check commands failed, restored the artifacts and confirmed success.

Documentation links/fences, checklist IDs/prior completion marks, the root
32 KiB instruction budget, source inventories, `git diff --check` and the
redacting source secret scan passed. Local database/process/subprocess execution
used automatically approved sandbox escalations. Existing owner configuration,
original datasets/course artifacts and publication/history blockers were preserved.

## Reproduction and limits

Use Python 3.12.14/uv 0.12.5 and Node 24.19.0/pnpm 12.8.1 with the checked-in
locks. Follow [isolated CI database/model setup](../../infra/ci.md#reproduce-the-database-and-model-checks-locally)
for a disposable PostgreSQL/pgvector database and pre-provisioned fixtures.
Never point acceptance tests at the user's application database.

From `backend/`, set `TEST_DATABASE_URL`, `TEST_MODEL_ROOT`,
`TEST_MINILM_ROOT` and `TEST_CLIP_ROOT` to those isolated/provisioned resources:

```bash
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
make check
```

From `frontend/` in a separate environment without backend secrets:

```bash
pnpm check
```

For focused API tests from `backend/`:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin \
  tests/integration/test_api_*.py tests/unit/test_api_*.py
```

The [backend API guide](../../backend/README.md#phase-8-http-contract) documents
setup, admin cookies/CSRF, private uploads, client replay handling and readiness.
Schema generation and drift commands are documented in the
[frontend contract guide](../../frontend/README.md#generated-api-contracts-phase-8).

No paid Groq/Tavily calls or pretrained model downloads were made in this phase.
The HTTP graph tests use fake inference and fixture embeddings with real
PostgreSQL, MCP tools and checkpoints; pretrained embeddings are covered by
separate offline regression tests. These tests verify API behavior, not measured
live provider quality/latency. [Phase 7 live acceptance](../phase7/README.md)
remains blocked by the recorded Groq HTTP 413 token limits. Phase 8 does not
resolve that blocker or satisfy the deferred full-release/browser acceptance gates.
