# OpenAI provider migration — 2026-10-04

OpenAI Chat Completions is the sole application inference provider, with
`gpt-4o-mini` as the independent text and vision default. The adapter uses the
existing pinned HTTPX client; the unused legacy SDK and LangChain provider
package were removed from the dependency manifest, lock and local environment.
LangChain Core is now an explicit pinned dependency for the graph's direct imports.

Configuration, API composition, ingestion previews, Compose, frontend secret
guards, telemetry, fake fixtures, smoke commands and project documentation use
`OPENAI_API_KEY`, `OPENAI_MODEL` and `OPENAI_VISION_MODEL`. The ignored local
`.env` retains the user's OpenAI key and unrelated settings; obsolete provider
assignments were removed and the independent vision default was added. No key
values were printed or committed. Historical evaluation JSON retains its original
provider/model identifiers and measurements; those runs are not OpenAI evidence.

The adapter sends non-streaming requests with `store=false` and keeps tool
selection separate from structured generation. Application schemas include
optional/defaulted fields and open mappings, so JSON Schema guidance uses
`strict=false`; Pydantic/domain validation and bounded repairs remain mandatory.
Refusals, content filtering and truncated completions fail safely. Existing
timeouts, concurrency limits, cancellation, retry/backoff, token accounting,
hard dietary exclusions and citation validation remain in place. Embeddings
still run locally; no model fallback was introduced.

## Verification

- Red/green regression: four failures demonstrated the old endpoint and missing
  refusal/truncation handling before implementation; the eight new HTTP contracts
  now pass with synthetic credentials.
- Backend `make check`: **471 passed, zero skips**, including real PostgreSQL
  16.14/pgvector, provisioned CPU fixtures and pretrained MiniLM/CLIP, both MCP
  transports, checkpoints, HTTP/SSE, catalog atomicity and provider contracts.
  Ruff/format, strict mypy and OpenAPI drift checks passed.
- Frontend `pnpm check`: generated types, ESLint, TypeScript, one component test
  and five configuration/build tests passed. OpenAI settings are rejected from
  the frontend environment without printing their values; built browser assets
  contain no synthetic private canary.
- Compose configuration passed with synthetic settings: only the backend receives
  the OpenAI key, and both model defaults resolve to `gpt-4o-mini`.
- `uv sync --locked --offline` removed the two obsolete packages. No new provider
  SDK was needed. Documentation, whitespace and redacting secret checks passed.
- Process-sandbox subprocess tests stalled or failed; bounded reruns outside that
  sandbox passed. PostgreSQL verification used the existing isolated test service,
  leaving the other local application's database untouched.

The owner explicitly authorized both live checks. The
[capability report](capabilities.json) records passing text and image probes on
`gpt-4o-mini`: two successful requests and 8,636 reported tokens, including image
input tokens. These probes establish access and schema-guided text/vision input,
not recommendation quality.

The [full graph report](live_graph_report.json) records real stdio MCP/pgvector
retrieval and PostgreSQL checkpoints with OpenAI inference:

| Measurement | Result |
| --- | --- |
| Seed query | Italian tomato/basil recipes with dated food trend context |
| Retrieved candidates | 16 recipes, one retrieval attempt |
| Recommendations | Five, all IDs and citation references validated |
| Checkpoint | Completed; temporary conversation/session cleaned by the smoke script |
| Graph duration | 78.96 seconds, within the 120-second limit |
| OpenAI attempts | 10 |
| Reported tokens | 127,671; timed-out requests may have unreported usage |
| Trend network searches | Zero; eligible cached Tavily evidence was available |
| Expert outcomes | Nutrition succeeded; style and trend were unavailable |
| Smoke result | Passed its recommendation/reference/checkpoint contract, with degraded experts |

All six stages executed and synthesis returned supported catalog recommendations.
The style stage reached the approximately 30-second call limit. Trend analysis
returned a typed unavailable outcome despite available cached evidence; the report
does not identify its exact cause. The run does **not** establish fully successful
expert analysis, fresh Tavily network access, follow-up quality or broad persona
quality. Full live acceptance remains open for those requirements. Historical
HTTP 413 failures are not attributed to OpenAI.

## Reproduce

From `backend/`, after configuring the ignored root `.env` and local services:

```bash
uv sync --locked
ENABLE_LIVE_OPENAI=1 make check-openai-capabilities
ENABLE_LIVE_GRAPH=1 make smoke-agent-graph GRAPH_SERVICE_ENV_FILE=/absolute/path/to/private-services.env
```

These explicit opt-in targets write this directory's JSON reports. Ordinary
checks and health endpoints make no paid provider calls. Rebuild the backend/MCP
images before running the migrated Compose stack; this verification did not
restart the user's application or build new deployment images.

Implementation references: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
and [image inputs](https://developers.openai.com/api/docs/guides/images-vision).

The root `.env` has working OpenAI settings, but the standalone backend syntax
check still reports missing `DATABASE_URL`, `MCP_SERVER_URL`, `MEDIA_ROOT` and
`ADMIN_PASSWORD_HASH`. Those unrelated setup values were not invented or copied
from the other application. The graph smoke used the existing ignored isolated
service configuration; it does not prove that the root `.env` alone can start the
full stack.
