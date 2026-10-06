# Phase 10 — Evaluation and hardening (P10-01–19)

Scope is P10-01 through P10-19. Deterministic acceptance providers are fake.
Separate opt-in live smoke and synthetic Cloud audits are recorded below.
Normal conversation telemetry remains disabled pending operational gates;
full-release work and existing blockers are preserved.

The [acceptance report](acceptance_report.json) was regenerated on 2026-10-06
during the [P11-08 local release review](../phase11/release-gate.md). It now binds
the current Phase 11 prompts/rules and fixture adapter after the P11-04 changes.
The ten cases, twelve turns, label/source hashes and expected outcomes are
unchanged; all grounding/constraint counters remain zero. Historical Phase 10
measurements below retain their original scope.

The four personas come from the local Module 3 multi-agent assignment PDF.
[Acceptance labels](acceptance.json) retain catalog IDs, exact source excerpts,
source hashes, explicit restrictions and expected outcomes. Health-conscious
preferences do not imply medical restrictions or measured nutrition. The family
allergy scenario abstains: this catalog cannot verify allergen absence.
Sparse positives are not exhaustive relevance judgments or provider-quality scores.

## Verification evidence

- P10-01: source/persona contract passed (1 test); hashes and excerpts checked
  against unchanged original JSON. Added the contract before fixtures (red/green).
- P10-02: 12 label/graph tests passed. Ten cases (12 turns) cover image
  routing, retained restrictions, explicit removal, strict vegan conflict,
  unknown restaurant allergy compliance, empty results and contradictory diets.
  Image routing uses fake media; real CLIP measurement is separate.
- P10-03: 13 label/graph tests passed. [Acceptance report](acceptance_report.json)
  records label/source hashes, exact prompt and rule file hashes, Git base revision,
  installed runtime versions and pinned embedding identities. Inference is explicitly
  fake and embeddings are not executed by this acceptance harness.
- P10-04: 6 label/metric tests passed; fresh CPU MiniLM/CLIP and exact
  PostgreSQL retrieval measured 25 queries × five settings × two executions.
  Corpus: 210 restaurants, 109 recipes, ten reviews, 770 text and 118 image
  vectors, including all 109 recipe and nine reviewed image associations.
  [Measurements](retrieval_report.json) and [baseline comparison](retrieval_comparison.json)
  preserve per-query/category ranks and metrics. Initial 0.6/0.4 gives Recall@20
  1.000, nDCG@5 0.965 and cuisine diversity@5 0.630 on all Phase 10 labels.
  The common 21-query comparison is recorded separately. Image-heavy recall
  drops to 0.977; initial defaults remain unchanged. Empty-label queries are
  excluded from recall/nDCG means, and identity-image limitations remain explicit.
  The importer still reports the existing 16 entity-review pairs, with no rejects.
- P10-05: 40 acceptance/label/constraint tests passed. Every fixture turn records
  zero fabricated recommendation IDs, unsupported citation IDs, duplicates and
  hard-constraint violations. Full-graph adversarial synthesis attempts forge an
  entity, citation or category and fail after one repair without publishing items.
  Canonical conflicts and unknown allergy compliance continue to abstain.
- P10-06: 53 claim/acceptance/expert/freshness tests passed. Negative tests
  first exposed publication of verbatim but unsafe upstream excerpts. A conservative
  core claim gate now rejects allergy guarantees, quantitative nutrients, unsupported
  operating/price/rating facts and catalog current-trend assertions in synthesis and
  style observations. Unsafe tool limitations are dropped; generated medical
  limitations remain replaced by deterministic text. Dated trends keep their separate
  freshness/association checks. This bounded phrase gate is not a universal semantic
  verifier; unknown culinary evidence remains unknown and no certification is claimed.
- P10-07: 53 injection/MCP/claim/acceptance tests passed. Poisoned review,
  caption and MCP-result citations cannot publish embedded instructions; a
  genuinely related, dated but injected web excerpt is rejected too. A malicious
  MCP server advertising deletion/secret-read tools gains no capability: its tool
  bodies never execute and extra result fields fail validation. A synthetic secret
  canary never enters inference contexts or outcomes. Runtime tool allowlists,
  typed arguments/results and absence of catalog-write/file/shell capabilities
  enforce authority independently of phrase detection or model obedience.
- P10-08: 51 tests and 64 configuration subtests passed. HTTP 429 retries honor
  Retry-After without switching models; credential/refusal/incomplete responses
  fail safely, malformed JSON/schema and capability mismatches share the bounded
  repair budget. Database/MCP downtime and invalid tool results produce dependency
  failure rather than no-match or fabricated fallback. Missing credentials,
  transport timeout, stale/undated trend evidence and readiness failures are covered.
- P10-09: 17 unit/API/PostgreSQL checks passed. Concurrent owned graph threads
  preserve different restrictions and opaque run IDs; restart keeps their histories
  isolated. Provider concurrency stays at three, and both deadlines and cancellation
  include the semaphore queue without dispatching cancelled work. Real PostgreSQL
  checkpoints verify restart, owner rejection, cancellation and separate adapters
  contending for one conversation lease. SSE disconnect/terminal persistence and
  run deadline/exclusion checks pass. Both real MCP transports also passed (2 checks)
  after applying migrations to the new test database.
- P10-10: 64 targeted security/upload/archive/API checks passed, including
  IPv4/IPv6 loopback, private/link-local and mixed DNS answers, rejected URL forms,
  redirect revalidation/pinning, malformed/oversized images, metadata stripping,
  unsafe ZIP paths/symlinks/expansion/CRC, media ownership and administrator
  login/logout/expiry/origin/CSRF. Additional scanner tests cover redacted match
  values, private dotenv preservation, example scanning and symlink rejection.
  Frontend generated contracts/format/lint/types, 25 component/unit tests and
  five private-environment/build tests passed; production build succeeded.
  Five real browser/API/PostgreSQL/HTTP-MCP journeys passed with fake providers,
  including uploads, admin CRUD/conflicts, restrictions and cancellation.
  [Redacted scan](security_scan.json) records zero findings in source and fresh
  built assets, with input manifest digests. CI now scans built frontend assets.
  Logging tests preserve operational IDs/counters and omit arbitrary message,
  exception, credential, profile, media and tool content. Only `.env.example`
  is tracked; existing local configuration and course artifacts are preserved.

## Combined verification and reproduction

On 2026-10-05 the combined offline backend unit/contract suite passed **372 tests
and 64 subtests**, with no skips. Ruff lint/format, mypy, OpenAPI drift, actionlint
and Git whitespace checks passed. Targeted real database groups above were run
before the separate browser harness populated the disposable test database.
The initial P10-01–10 suite made no OpenAI/Tavily/live smoke calls; later
opt-in checks are recorded separately below.
Full release, live trend evidence and historical publication review are unchanged
release gates. Source scans detect known token patterns, not arbitrary secrets.

From `backend/`, use `make test-phase10` for the focused deterministic suite and
`make evaluate-acceptance` to regenerate the graph report. `make
evaluate-phase10-retrieval` uses explicit `DATABASE_URL`, `MINILM_ROOT`,
`CLIP_ROOT` and `MEDIA_ROOT` against a seeded catalog with validated associations;
it runs the existing exact PostgreSQL/CPU evaluator and the baseline comparison.
The pinned pretrained models/media remain local and ignored. Recreate only a
fresh disposable `foodwise_test` service for database tests, then run
`tests/integration/test_agent_checkpoints.py`, `test_api_messages.py`,
`test_api_workflow.py`, `test_api_admin_auth.py`, `test_api_conversations.py`,
`test_api_media.py`, `test_api_admin_catalog.py` and `test_mcp_protocol.py` with
`TEST_DATABASE_URL` configured. MCP protocol tests require applied migrations.
The frontend `pnpm check`, `pnpm build` and `pnpm test:e2e:integration` commands
follow [the existing isolated harness instructions](../phase9/README.md).
Finally, from the repository root:

```bash
python scripts/scan_secrets.py --build-root frontend/.next --output evaluation/phase10/security_scan.json
```

The isolated local service used port 55440. It was stopped after verification;
no owner's database/service or source dataset was changed. Earlier setup checks
found missing migrations and missing cached review-image associations; both were
corrected before the passing evidence above was recorded.

## P10-11 — Local performance

[Performance report](performance_report.json) records 120 real-graph fixture
turns: p50 14.85 ms, p95 23.13 ms, with six stage distributions and actual
fixture attempt/search counts. Provider tokens remain unknown, rather than
claiming fixture zeroes measure live usage. Fresh-process CPU MiniLM/CLIP
loads took 8.53/6.89 s; warm text encode p50 17.76/49.43 ms; peak process RSS
490.65/975.54 MiB. Machine, CPU time, single-thread configuration and first
encode measurements are in the report. OS page-cache temperature is uncontrolled.
Graph measurements exclude DB, browser and provider/network latency; embedding
probes run separately. This is a reproducible local baseline, not live service
performance. One summary contract passed after its initial missing-module failure.
Run `make measure-phase10` with the ignored pretrained model directories present.

## P10-12 — Separate offline and live checks

[Verification manifest](verification_report.json): 373 unit/contract tests;
172 integration tests, with the two initially skipped pretrained tests rerun
successfully; 25 frontend unit tests, five configuration checks, ten production
browser/accessibility checks (54.0 s), and five real API/PostgreSQL/HTTP MCP
journeys (1.2 min). Ruff, format, mypy and OpenAPI drift passed. External
network is blocked in normal pytest fixtures. Tests used isolated port 55440.

Explicit live checks are separate: [text/vision capability probes](live_openai_capabilities.json),
[dated Tavily smoke](live_trends_smoke.json), and [six-agent graph smoke](live_graph_smoke.json)
passed. The graph took 26.80 s, eight actual model attempts, 12,580 reported
tokens and one live search; it retrieved one real candidate. Style and trend
analysis were unavailable, so this is a degraded integration check and does not
close full-release acceptance. The independent trend smoke returned dated
evidence. Initial trend configuration failures were corrected by explicitly
selecting the disposable database and local media. No owner service was changed.
Physical-device/spoken assistive-technology testing remains unavailable.

## P10-13 — Package and ORM contracts

The 13 existing package/cold-registration contracts and 23 acceptance contracts
passed together (36 tests, 5.14 s). The SDK denylist now explicitly includes
Langfuse and OpenTelemetry, preventing future core/agent imports. Reviewed
provider, media, persistence and embedding adapters retain narrow core ports;
core modules import in both orders without cycles; fresh ORM registration
resolves all 20 tables and foreign keys without loading adapters/models.
Existing graph/API contracts continue to reject concrete I/O leakage.
Static checks and OpenAPI drift passed. New telemetry cold-import checks are
recorded with their implementation in P10-15.

## P10-15 — Optional tracing infrastructure

A narrow recommendation observation port has injected no-op defaults; SDK/OTel
imports remain lazy inside `infrastructure/telemetry`. Composition owns the
process client and shutdown. Disabled tracing does not construct the SDK, open
sockets or start exporter threads. Credentials alone never enable exports; the
conversation deletion/retention verification flag remains false by default.

Explicit sanitized scopes exclude graph content, exceptions and automatic
framework callbacks. The final OTLP exporter rebuilds spans, discarding all
events, links, resources, exception status text and nonallowlisted attributes.
Network exports have a two-second timeout and 256 KiB request bound; batch size
is 32 and SDK queue is bounded at at most 2,048 observations. Shutdown has a
three-second application wait and uses a daemon worker, so a hung exporter
cannot occupy the asyncio default executor during process exit.

18 lazy initialization/privacy/package tests passed, including serialized real
SDK OTLP with fake export and injected private input/output/metadata/events.
Mypy passed (169 source files); OpenAPI remains unchanged. SDK internals still
start background managers when enabled; overhead is measured in P10-19.

## P10-16 — Executed observation hierarchy

One `recommend-food` chain covers each accepted traced graph turn; the six
executed roles emit sibling agent observations. Clarifications only create
executed stages. OpenAI generation observations wrap each actual HTTP attempt
after semaphore acquisition; successful responses supply their own usage and
failed attempts leave usage unknown. Retry ordinals are task-local. MCP tool/
retriever observations cover each backend gateway attempt, without remote
server spans or extra tool arguments. No LangChain callbacks duplicate scopes.

Opaque run IDs map to 32-character trace IDs; keyed HMAC conversation grouping
is propagated with environment and implementation revisions through the SDK
v4 attribute context. Raw session/thread/ownership identifiers are excluded.
Results, requests, prompts and graph state never enter observation creation.
Explicit outcomes cover failure, exhaustion, clarification and cancellation.

61 trace-tree/retry/usage/agent/acceptance/boundary tests passed, following the
initial missing-root red failure. A real SDK with fake OTLP export verifies
six sibling stages, one synthesis, propagated opaque session and two generation
observations for one 429 followed by success, with usage recorded once. Mypy
passed. Cloud read-back and expanded concurrency/privacy checks are P10-17.

## P10-17 — Tracing isolation and Cloud audit

15 offline SDK/exporter contracts pass: unchanged fixture results under actual
mocked OTLP HTTP 401/429/503 and timeout responses; isolated concurrent trace
parentage; early clarification; retries, schema repair and cancellation; no
SDK imports/threads/network while disabled; bounded cursor pagination; and a
saturated 32-observation test queue that drops spans without blocking work.
Serialized privacy checks cover inputs, outputs, metadata, events, exceptions
and media sentinels. Core/static checks and schema drift pass.

[Current Cloud audit](langfuse_cloud_audit.json) verifies eight synthetic traces
(full graph, follow-up turns, clarification, retry, schema repair, cancellation)
through Observations v2, with bounded polling/pagination and stored type,
parentage, content, usage, opaque session, run/revision and duration checks.
Exact trace references remain ignored/private for targeted cleanup. No paid
inference, dataset upload, raw content or ordinary conversation export occurs.

The execute/fetch/audit loop found and fixed: SDK synthetic-root parentage;
SDK floating-point metadata serialization; v4 propagated trace-metadata
allowlisting; the server rejecting `parseIoAsJson=true` despite the published
parameter; and proxy support in the default OTLP transport. The corrected
exporter uses a requests session. Current API returns raw IO strings; empty
fields are audited directly. SDK 4.16.0/current REST schemas are the tested
developer tooling; no CLI was installed or required. Actual quota exhaustion
was simulated, not induced against the Hobby account. Normal conversation
export remains disabled pending the P10-19 lifecycle gate.

## P10-18 — Local scores and current Cloud score audit

[Metric definitions](score_manifest.json) bind ranges, targets, denominators
and evaluator revision. [Score report](score_report.json) covers 12 fixture
turns with 22 locally computed applicable scores; no fabricated ID or hard
constraint violation was observed. Inapplicable citation/constraint metrics
are omitted rather than exported as passing zeroes. Retrieval quality and
aggregate latency remain local report metrics, without falsely associating
them with different synthetic graph retrieval.

19 score/tracing tests pass, including same-ID retry upsert, shared trace
sampling decisions, private fixture-reference hashing and a guard against
invoking hosted dataset/Experiment helpers. Inputs, expected/task outputs,
images, comments and judges remain local/excluded. Native experiments are
not enabled because local-data helpers can export content.

A synthetic US Cloud export sent each score twice with the same explicit ID.
Scores v3 read-back verified exactly 22 stored unique scores, exact values,
observation/trace associations and allowed metadata, with no comments. Cloud
links and IDs remain ignored/private. Normal conversation export stays off.
Short-lived scripts use bounded flushing outside request handling; the first
per-case network flush exceeded its deadline and was replaced by one bounded
final export flush. Offline reports and deterministic gates are independent
of all telemetry results. Run `python -m scripts.export_phase10_scores` from
`backend/`; add `--enable-cloud` only for a deliberate synthetic Cloud audit.

## P10-19 — Resource limits, sampling and deletion

[Predeclared limits](telemetry_limits.json) preceded the experiment.
[Initial run](telemetry_overhead_initial.json) missed the 25% relative warm
p95 latency threshold (34.66%, 7.91 ms), while memory stayed within its limit.
Buffering per-observation SDK updates reduced repeated attribute writes.
[Measured rerun](telemetry_overhead_report.json), with 100 warm samples/mode
in fresh processes, passed the unchanged limits: disabled/enabled p95
31.42/33.17 ms, additional peak RSS 25.73 MiB, cold first turn
24.42/239.54 ms, maximum batch 32 observations/20,882 serialized bytes.
Enabled export produced 1,414 observations in 45 calls/912,065 bytes. These
are synthetic timings on one host with uncontrolled page cache/load; the
changed baseline and p50 distributions are retained, without claiming universal
or causally isolated performance gains. Remote wire headers/compression and
existing Cloud quota consumption remain unknown.

The pilot gives 14 observations/turn. At a hypothetical 100 turns/day plus
three applicable scores/turn, estimated monthly volume is 54k units; whole
trace sampling at 0.5 reduces the forecast to 27k, below the declared 80%
Hobby allowance budget. These are forecasts, not billing measurements. Sampling
tests prove parent/child and score decisions match; local acceptance remains
fully evaluated regardless of sampling. Queue saturation and privacy contracts
continue to pass.

Five focused deletion/sampling/SDK-logging checks pass. The local opaque SQLite journal
retains trace mappings and permanent HMAC-session tombstones across restart.
Conversation erasure queues trace deletion without changing API results;
export filtering holds a bounded interprocess lock so in-flight delivery
precedes tombstoning and later queued exports are suppressed. Journal lock
contention is retried for up to three seconds. Supported remote purge/retry
is explicit developer tooling, never an MCP agent tool.
[Cloud purge](langfuse_purge_report.json) submitted 51 locally recorded
synthetic trace IDs and verified no matching recent observations or associated
22 scores remained after two polls. This proves the scoped recent pilot purge;
it does not prove automatic retention or extended delayed ingestion.

**Operational gates remain open:** Hobby has no retention policy; automatic
purge scheduling, old inaccessible history, provider backup semantics, failed
journal persistence recovery and long delayed-ingestion behavior are not
verified. `LANGFUSE_ENABLED` and `LANGFUSE_CONVERSATION_EXPORT_VERIFIED` remain
false for normal use. This scoped task records implementation, measurements,
checks and gaps; it does not declare operational readiness or close Phase 11.
The first Compose smoke invocation was sandbox-blocked; the later quiet
configuration check passed with synthetic values. A full Compose runtime
rehearsal remains Phase 11 rather than being claimed here.

## Final P10-11–19 verification

On 2026-10-05, the full backend suite passed **571 tests with zero skips**
(68.15 s), with real PostgreSQL/pgvector, both MCP transports, checkpoint
persistence and separately provisioned MiniLM/CLIP fixtures. The initial
combined run passed 569 tests and exposed one stale acceptance implementation
hash; regenerating the 12-turn report resolved it before the passing rerun.
A later cold-SDK logging review found an SDK-added plain httpx handler; the
adapter now preserves application handlers, and **38 affected tracing, SDK
privacy, deletion, sampling, score and package contracts passed** afterward.
Ruff lint/format, strict mypy (173 source files), OpenAPI drift, Compose quiet
configuration with synthetic values, 175 local documentation links, balanced
fences and unique checklist IDs passed. [Final source/build scan](security_scan_final.json)
found zero known secret-pattern matches in 2,710 files. Earlier P10-12 frontend
and browser results remain recorded above; no UI/contracts changed afterward.

All nine requested tasks have dedicated commits on the current Phase 10 branch.
Normal telemetry and Phase 11/public-release gates remain as documented. The
disposable test service is stopped after verification; owner services, local
credentials, original datasets and course media are preserved.
