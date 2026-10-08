# Langfuse adoption plan

Assessment: 2026-10-05; operational rehearsal updated 2026-10-08. Status: scoped
implementation and P11-12 synthetic demonstration verified; P11-11 remains open
and normal conversation export disabled.
The owner selected Langfuse Cloud with sanitized operational metadata, replacing
the initial self-hosting preference after reviewing local RAM constraints.
Work is tracked in [Phases 9–11](../CHECKLIST.md#phase-9--nextjs-frontend-and-administration).
The owner explicitly requested P10-11–19 implementation on 2026-10-05.
The historical planning sections below describe the reviewed design.

## Fit for foodwise-ai

Langfuse is suitable for tracing and evaluating the recommendation workflow.
Its [LangChain/LangGraph integration](https://langfuse.com/integrations/frameworks/langchain)
supports callbacks, and its [Python SDK](https://langfuse.com/docs/observability/sdk/overview)
supports explicit observations. This makes an incremental integration possible
without replacing the six-agent graph, retrieval, persistence or API contracts.
Compatibility with this repository's locked versions still needs verification.

| Existing capability | Useful observability | Integration location |
| --- | --- | --- |
| Six stages and parallel expert join | Stage duration/outcome, overlapping experts, one synthesis | Injected callbacks at `GraphRunner` invocation |
| Bounded OpenAI inference and repairs | Each attempt, model, duration, reported tokens, typed failure | Explicit observations in the provider adapter |
| MCP retrieval and trends | Tool name, duration, attempts, result count, unavailable outcome | Injected wrapper around `ToolGateway` |
| Persistent follow-ups | Separate trace per turn, grouped by an opaque conversation correlation | Runner context, separate from ownership tokens |
| Source-backed evaluation fixtures | Compare revisions and inspect failing cases | Evaluation scripts and optional local score export |

The existing [runner](../backend/src/food_recommender/agents/runner.py),
[stage telemetry](../backend/src/food_recommender/agents/telemetry.py) and
[run budgets](../backend/src/food_recommender/application/recommendations/reliability.py)
already provide run IDs, stage outcomes and counters. Preserve these as the local
source of operational evidence. The [OpenAI adapter](../backend/src/food_recommender/infrastructure/providers/openai.py)
uses `httpx`, not the OpenAI SDK or `ChatOpenAI`: a graph callback alone will not
capture provider generations or usage. Instrument actual request attempts in
that adapter; do not switch provider libraries just to obtain tracing.

Langfuse can store [custom scores](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk)
and [versioned evaluation datasets](https://langfuse.com/docs/evaluation/experiments/datasets).
Our local evaluators must still calculate grounding, hard-constraint adherence,
Recall@20, nDCG@5 and diversity. Traces alone do not establish recommendation
quality, dietary safety or course acceptance.

## Review against the Langfuse skill

Reviewed the upstream [Langfuse skill](https://github.com/langfuse/skills/blob/main/skills/langfuse/SKILL.md)
and relevant references on 2026-10-05. These links track `main`; re-read the
applicable guides and current SDK/API documentation at implementation time and
record the reviewed skill revision with the implementation evidence. The skill
is development guidance, not a runtime dependency. No skill installation or
Langfuse project access was performed for this review.

| Guide | Application to this plan |
| --- | --- |
| [Instrumentation](https://github.com/langfuse/skills/blob/main/skills/langfuse/references/instrumentation.md) | Define observation names/types and parentage; run, fetch, audit and repeat before claiming completion. |
| [Current trace best practices](https://langfuse.com/docs/observability/best-practices) | Stable operation names, useful filtering dimensions and one trace per turn; preserve the metadata-only policy. |
| [v4 preparation](https://github.com/langfuse/skills/blob/main/skills/langfuse/references/v4-project-migration.md) | Use current observation APIs and propagated attributes; verify Cloud ingestion separately from repository tests. This is a new integration, so historical migration is unnecessary. |
| [Evaluation setup](https://github.com/langfuse/skills/blob/main/skills/langfuse/references/setting-up-evals.md) | Start with the existing offline acceptance metrics and explicit score definitions; no hosted evaluators or judge configuration. |
| [Dataset construction](https://github.com/langfuse/skills/blob/main/skills/langfuse/references/create-dataset.md) | Review source-backed expected results and keep fixture inputs, expected outputs and metadata distinct locally. Generated labels alone are not ground truth. |
| [CLI](https://github.com/langfuse/skills/blob/main/skills/langfuse/references/cli.md) | Discover current resource schemas and use scoped observation queries for the opt-in audit; no project credentials are needed for planning. |

Some upstream recommendations assume content-rich traces: message input/output,
reasoning content, media and hosted prompts. Those conflict with the selected
Cloud data policy and remain excluded. Cloud traces will explain execution,
timing and measured scores; content-level investigation stays local. Framework
callbacks are preferred only if they pass the privacy and hierarchy checks below.

## Cloud configuration and compatibility gate — P10-14

Use a dedicated Langfuse Cloud project. Langfuse operates the web/worker and
storage infrastructure, so this approach avoids adding those services to the
developer's machine. The [deployment guide](https://langfuse.com/self-hosting/deployment/docker-compose)
confirms Cloud and self-hosting use the same SDKs/integrations. The historical
[host assessment](memory-assessment.md) records 6.538 GiB RAM; Cloud addresses the
additional hosting burden, not existing MiniLM/CLIP memory use. Measure SDK/export
buffer overhead before enabling tracing in any development profile.
No Langfuse containers, database migrations or media volumes are needed locally.

Before setup, record the owner's chosen Cloud region and plan, current quota,
rate limits, access/retention terms and deletion capabilities. Region and plan
remain implementation-time decisions; do not silently use an SDK default region.
Start by assessing the free Hobby plan against measured trace volume. Its
[current pricing](https://langfuse.com/pricing) has usage and data-access limits;
do not assume unlimited storage, configurable retention or that one run equals
one billable unit. Estimate units per run, monthly volume and sampling needs from
a synthetic pilot. Paid subscriptions or upgrades require separate authorization.

Use the selected region's explicit HTTPS base URL and project-scoped keys in
ignored server-side configuration, never `NEXT_PUBLIC_*`. Proposed configuration
is `LANGFUSE_ENABLED=false`, `LANGFUSE_BASE_URL`, `LANGFUSE_PUBLIC_KEY` and
`LANGFUSE_SECRET_KEY`; document and validate these only when implementing them.
Keep runtime and test projects distinct; ordinary CI has no Cloud credentials.
Pin and lock tested SDK/OTel dependencies after checking Python 3.12, LangGraph,
LangChain Core and existing dependency compatibility. The managed server version
is not under project control, so document the tested date and client versions.

The concrete Python SDK candidate is `langfuse==4.16.0`, the
[latest stable release found in this review](https://github.com/langfuse/langfuse-python/releases/tag/v4.16.0).
It is not installed or compatibility-tested here. Check it against the current
`langgraph==1.2.12`, `langchain-core==1.6.6` and resolved
`opentelemetry-api==1.45.0`; record the resolved exporter/SDK versions in the lockfile.
Recheck releases when P10-14 starts and revise this candidate explicitly if needed.
The [compatibility schedule](https://langfuse.com/docs/compatibility) currently
sets 2026-11-16 for removal of legacy Cloud APIs/ingestion. Target Python SDK v4
and current APIs from the outset; an older SDK is not an assumed rollback option
after that cutoff. Rehearse disabling tracing as the fallback.

Telemetry will leave the machine for the selected region. Apply the data policy
below before export and inspect the actual serialized payloads. Review Cloud
[region, access and deletion controls](https://langfuse.com/security) during setup;
opaque identifiers are still linkable operational data, not a claim of anonymity.
Keep the Langfuse Assistant, LLM judges, prompt hosting, external integrations and
media uploads outside this initial scope. Do not give Langfuse OpenAI/Tavily keys.
Cloud outages, offline development, invalid keys or quota exhaustion must leave
recommendation behavior unchanged; no automatic alternative telemetry destination.

## Integration boundaries — P09-13, P10-15–16

Phase 9 continues without a browser SDK, trace dashboard, feedback API or new SSE
fields. Preserve server-generated run IDs through the existing proxy and verify
streaming/cancellation. The Langfuse UI is a separate developer tool.

In Phase 10, add focused infrastructure modules, proposed as
`infrastructure/telemetry/{config,langfuse,redaction}.py`, wired through
`composition.py` and process lifecycle hooks. Keep the existing
`infrastructure/observability.py` logging module. Do not import Langfuse/OTel into
`domain`, `application`, `retrieval` or `ingestion`. Inject a callback factory into
the runner; add a narrow provider-neutral observation port only where an actual
consumer needs it, beside recommendation contracts. Preserve the SSE progress
observer's existing responsibility.

Default tracing off, with a no-op implementation. Initialization must be explicit
and lazy; ordinary imports, schema export, tests and health checks must not contact
Langfuse. When enabled, use a process-owned client, bounded asynchronous export,
finite timeouts/queues and bounded shutdown flushing. Do not flush per request or
await telemetry delivery before SSE completion. Export failure drops telemetry
with safe diagnostics and never changes recommendation, retry, lease or checkpoint
behavior. Cancellation must still propagate. Preserve existing logging setup and
avoid automatic global HTTP/SQL instrumentation.

Start with one trace per accepted recommendation run. Use the existing run UUID
as correlation metadata with an SDK-compatible trace ID. Group follow-ups using
a keyed opaque conversation identifier, never the browser session/ownership ID.
Keep parent context isolated across concurrent runs and restore it in `finally`.
The three experts are sibling observations under the run, not serialized spans.
Attach allowlisted build, prompt, model, embedding and dataset revisions.

### Observation contract

Use [specific observation types](https://langfuse.com/docs/observability/features/observation-types)
with this proposed mapping. Only steps actually executed produce observations;
an early clarification must not fabricate six completed stages.

| Operation | Stable name | Type and parent |
| --- | --- | --- |
| Accepted turn | `recommend-food` | Root `chain` |
| Six domain roles | `build-profile`, `retrieve-candidates`, `analyze-trends`, `analyze-style`, `assess-nutrition`, `synthesize-recommendations` | `agent`, under the turn |
| Actual OpenAI attempt | `request-structured-response` | `generation`, under its executing agent |
| Catalog search MCP attempt | Existing allowlisted search tool name | `retriever`, under the retrieval agent; represents only the client round trip |
| Other MCP attempt | Existing allowlisted tool name | `tool`, under its executing agent |

Keep model names, attempt numbers and run IDs in fields/metadata, not observation
names. Choose either the callback or an explicit wrapper to own each observation;
do not emit both for the same stage or invocation. Verify the resulting tree,
including repair calls and the parallel join, against actual execution.

Follow the [Python v4 attribute model](https://langfuse.com/docs/observability/sdk/upgrade-path/python-v3-to-v4):
use an enclosing observation and `propagate_attributes()` around graph execution.
Propagate the opaque conversation correlation as Langfuse `session_id`, the run
reference, revisions, environment and fixed feature tags to applicable children,
including cost-bearing generations. Never pass `GraphState.session_id` or
LangGraph's raw `thread_id` as telemetry session metadata. Omit `user_id` because
v1 has no multi-user identity requirement. Use bounded string values for propagated
metadata (currently at most 200 characters per value); keep numeric measurements
on their observations. Set known tags at creation and terminal outcomes separately.
Do not use removed `update_current_trace()` or `CallbackHandler(update_trace=...)`
examples. Verify that span filtering retains intended parents without exporting
unrelated OTel activity; filtering alone does not sanitize payloads.

Capture provider usage from each response directly, not by differencing the
adapter's shared usage list. Separate model attempts, repair attempts and tool
attempts; count each once. Missing failed-call tokens or Tavily credits remain
unknown. Monetary costs, if added, are estimates with a dated pricing source;
they are not billing records. Initially tool observations cover the backend's MCP
round trip only. Do not claim remote SQL, embedding or Tavily spans, or automatic
context propagation through HTTP/stdio; deeper server tracing requires a later
transport-specific design and tests without adding tool arguments.

## Data policy and verification — P10-17–19

Export only allowlisted identifiers, revisions, stage/tool/model names, durations,
counts and typed outcome/error codes. Exclude messages, prompts, graph state,
profiles/allergies, review/source text, tool arguments/results, images/base64,
model reasoning content, file paths, headers, cookies, credentials and
exception/stack text. Enforce this policy before any network transmission.
Keep prompt templates versioned in Git.

Disable automatic input/output and media capture before attaching callbacks.
Test the selected SDK's callback payloads; if safe filtering is not possible,
use explicit sanitized observations instead. Apply an export-stage allowlist as
defense in depth, including attributes, events, resource metadata and names.
Current [masking guidance](https://langfuse.com/docs/observability/features/masking)
provides `mask_otel_spans`, but media handling can precede that hook: masking is
not a substitute for preventing sensitive capture and upload at the source.
On filtering failure, discard affected telemetry instead of sending raw values.

| Verification | Acceptance evidence |
| --- | --- |
| Disabled, enabled and unreachable exporter | Same fixture results, IDs/citations, SSE sequence, persistence and cancellations; no export network/thread activity when disabled |
| Parallel and failed runs | Isolated parentage, one root per run, one synthesis when reached, terminal failure/cancelled spans and no duplicate usage |
| Privacy and injection | Synthetic sentinel secrets/private text absent from serialized exports, media uploads, SDK diagnostics and stored traces |
| Bounded failures | Offline access, invalid keys, Cloud 429/quota exhaustion, slow/refused exports and full queues preserve run deadlines, leases and bounded shutdown |
| Compatibility | Locked SDK resolution, package contracts, all affected tests, schema drift and existing offline CI pass |
| Observation contract | Stable names/types, propagated session/environment/revisions, no duplicate callbacks or orphan children, and correct early-exit coverage |
| Evaluation export | Fixture inputs, expected outputs, task outputs and score comments remain absent from every export path; retried scores do not duplicate measurements |
| Resource overhead | Repeated disabled/enabled runs with fake providers; compare p50/p95 latency, CPU/RAM, queue size, export traffic and trace loss against a threshold recorded before the experiment |

Build and test instrumentation first with an in-memory/fake exporter and existing
fake provider/tool boundaries. The live Cloud Langfuse smoke is a separate opt-in
test; ordinary CI needs no Langfuse service or credentials. Use a known synthetic
run and verify both stored spans and sanitized export payloads. Paid provider smoke
tests remain separately authorized and bounded.

The Cloud smoke must execute, flush with a deadline, fetch observations by its
known trace ID, audit them, and repeat after fixes. Cover a full six-stage run,
follow-up, early clarification, retry and cancellation using synthetic fixtures
and fake providers. Refresh the upstream best-practices page for this audit and
record intentional content omissions. Use the
[current Public API](https://langfuse.com/docs/api-and-data-platform/features/public-api)
through the CLI's discovered `observations` resource, with cursor pagination and
selected field groups; do not build read-back on legacy trace-list endpoints.
Audit content fields too in the synthetic privacy check. Allow bounded polling
for ingestion visibility; a successful flush does not prove stored completeness.
Keep trace links private and include sanitized audit evidence in local reports.
Discover and pin a tested CLI version during implementation; run it only as
developer tooling, outside application requests and ordinary CI.

Keep `evaluation/` fixtures and reports authoritative and runnable offline.
Export fixture references, revisions and locally calculated scores to the Cloud
project. Keep evaluation inputs, expected outputs, image bytes and user content
local in this initial metadata-only scope. Use locally executed experiments with
sanitized trace/score associations; hosted dataset content uploads need a separate
scope decision. Attach experiment/trace IDs to optional reports without changing
runtime recommendations. Record failed/skipped evaluations, denominators and
unknown metrics. LLM-as-judge and remotely managed prompts are outside this first
integration; neither replaces deterministic acceptance gates.

The [Experiment SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)
automatically traces tasks, and **local-data experiments still export experiment
data**. Do not pass raw fixtures/results to `run_experiment()` assuming they stay
local. Start with explicit sanitized observations and score export. Enable native
experiment helpers only after captured export tests prove the same policy for
inputs, expected outputs, outputs, metadata, errors and evaluator comments;
otherwise retain local experiment reports with correlation metadata in Cloud.
Finish short-lived export scripts with bounded flushing, outside request handling.

Before exporting, define each existing metric's stable name, type/range, target,
denominator, evaluator revision and decision in the local evaluation manifest.
For example, Recall@20 targets retrieval; citation correctness and constraint
violations target the final outcome; p50/p95 are report-level aggregates. Missing
labels and inapplicable cases must not become a zero or passing score. Use the
[score API](https://langfuse.com/docs/evaluation/evaluation-methods/scores-via-sdk)
with both trace and observation IDs when scoring an observation. Test an explicit
deduplication key per experiment execution, fixture, metric and evaluator revision
so export retries cannot inflate results. Free-text score comments remain excluded.

Use [trace-level sampling](https://langfuse.com/docs/observability/features/sampling)
if the pilot shows it is needed. Keep the bounded synthetic audit fully sampled;
for normal enabled runs, record the rate and verify children and associated score
exports follow the same decision. Independently exported scores require their own
check against that decision. Distinguish sampled-out traces from failed delivery.
Local acceptance metrics always use the full fixture set, regardless of sampling.

## Operations and completion — P11-11–12

Document project/region setup, enable/disable, credential rotation, quota checks,
SDK upgrades and rollback. Record the chosen plan's actual retention and deletion
semantics; a data-access window does not prove deletion. Select a retention policy
the plan can enforce, with a tested purge procedure where supported. If required
deletion cannot be verified, leave conversation-linked export disabled and record
the limitation. Conversation deletion must remove linked traces and queued
exports, with a local retry mechanism during outages; document the provider's
backup/deletion limits and verify deletion is not undone by delayed delivery.
Do not retain content merely to simplify debugging.

Keep reproducible fixtures and reports locally; Cloud dashboards are not the sole
copy of evaluation evidence. Existing application backup/restore stays unchanged.
Rehearse application operation with Cloud unreachable and tracing disabled.
Keep sanitized screenshots/reports and exact tested client versions with Phase
10/11 evidence. A passing Cloud tracing demonstration completes the Langfuse
tasks; unavailable credentials, quota or unverified privacy controls remain unchecked
and are explicitly recorded as optional observability limitations. Existing
culinary correctness and complete-release gates remain unchanged.

Initial planning verification on 2026-10-05: 99 local documentation links/anchors and
balanced code fences passed; all 143 prior checklist marks were preserved and
nine new tasks remain unchecked. Instruction-size and whitespace checks passed.
Only this plan and `CHECKLIST.md` changed. No runtime tests were needed for this
documentation update; SDK compatibility, Cloud access and performance remain
future verification work.

Skill-review verification on 2026-10-05: all 100 local documentation
links/anchors, code fences, whitespace and instruction-size checks passed.
All 152 checklist IDs and completion marks present before this review were
preserved. Changes remain limited to this plan and `CHECKLIST.md`; no runtime
code, dependencies or configuration changed. The SDK candidate and Cloud audit
remain unverified implementation work, not completed integration evidence.

## P10-14 feasibility evidence — 2026-10-05

[Sanitized feasibility report](../evaluation/phase10/langfuse_feasibility.json).
Existing dedicated US project keys in ignored `.env` returned HTTP 200 and
one project; no new account, paid subscription or local stack was created.
The owner confirmed Hobby with no retention policy. The
[Hobby limits](https://langfuse.com/pricing) are 50k monthly units and a 30-day
access window; project quota consumption is not exposed by project-scoped keys.
[Retention](https://langfuse.com/docs/administration/data-retention) management
is unavailable on Hobby. This access window does not purge data.
[Single/batch deletion](https://langfuse.com/docs/administration/data-deletion)
is supported but asynchronous, with read-back required. Conversation exports
remain disabled until durable deletion/retention controls can be demonstrated;
synthetic audit exports are separately bounded.

Pinned `langfuse==4.16.0` resolves with Python 3.12.14, LangGraph 1.2.12,
LangChain Core 1.6.6 and OpenTelemetry API/SDK/exporter 1.45.0. `uv pip check`
passed for all 157 installed packages. Current
[compatibility](https://langfuse.com/docs/compatibility) still sets the legacy
Cloud cutoff at 2026-11-16. New reads target Observations v2; trace DELETE
remains a supported mutation despite trace GET deprecation. SDK disable is
the supported rollback. No CLI or Experiment helpers are required by the
application; their content-export behavior remains excluded.

## P10-15–19 implementation evidence — 2026-10-05

[Phase 10 evidence](../evaluation/phase10/README.md) records lazy no-op defaults,
explicit SDK scopes, allowlisted/rebuilt OTLP, bounded failures, current
Observations v2 and Scores v3 audits, same-ID score retries, local reports,
SDK resource limits, sampling and targeted synthetic purge. No framework
callbacks, native experiments, hosted datasets/prompts/judges or content
export were enabled. No additional Cloud plan or local stack was purchased.

Normal conversation export remains disabled. Hobby has no configured automatic
retention; the local tombstone journal supports delayed-queue suppression and
explicit developer purge/retry but does not prove automatic scheduling, old
inaccessible-history deletion, failed-journal persistence recovery, provider
backup behavior or long delayed-ingestion completion. Phase 11 operational
rehearsal remains open. Application correctness and local reports are independent
of these observability gaps.

## P11-11/12 rehearsal — 2026-10-08

The [operations guide](langfuse-operations.md) and
[Phase 11 evidence](../evaluation/phase11/README.md#p11-1112--optional-cloud-operations-and-demonstration)
record fresh US-project access, 20 private synthetic demonstration traces,
current API/CLI observation and score audits, scoped deletion and application
acceptance with disabled/unavailable export. Python SDK 4.16.0 is the unchanged
application pin; 4.17.0 upgrade and 4.16.0 rollback are tested in isolation.
CLI 1.2.4 and upstream skill revision
`104acd9aa7b1f431066cd9fe4b0b431a0188e642` are reviewed/tested on 2026-10-08.
P11-12's recording scope passes. The new 100-sample SDK latency measurement
misses the unchanged 10 ms/25% overhead limits; account quota/key revocation,
retention/purge scheduling, journal recovery and extended deletion controls
remain unverified. Live journal/export contention can drop tracing, so the
synthetic audit explicitly uses deferred bounded delivery. P11-11 and normal
conversation export remain open/off; existing local application acceptance
and historical Phase 10 evidence are preserved.
