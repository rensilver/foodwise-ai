# Phase 6 — MCP services and live food trends

Verified on 2026-10-03. Each P06 task has a separate commit on
`feature/phase6-mcp-services-food-trends`.

The independent FastMCP process exposes seven typed read-only tools and three
fixed public catalog resources. Restaurant names report ambiguity, vibe searches
use structured ambiance plus descriptions, and review retrieval requires explicit
demo scope. Search tools reuse the Phase 4/5 services, constraints, entity links,
canonical ingredients and citations. Missing models return dependency errors.

The application client discovers schemas once per connection and validates inputs
and outputs. Six fixed role allowlists, application-supplied run/session/demo IDs
and a configured endpoint bound capabilities. There is no sampling callback,
Groq inference, arbitrary server/tool selection, SQL, filesystem path or mutation
tool. Media reads enforce ownership, validated basenames and `O_NOFOLLOW`; Compose
keeps MCP internal and mounts model/media directories read-only. Roots do not
enforce these restrictions.

| Evidence | Verified behavior |
| --- | --- |
| [Catalog protocol report](catalog_protocol_report.json) | Real CPU MiniLM/CLIP and PostgreSQL retrieval over subprocess stdio and actual Streamable HTTP; matching restaurant/recipe/image IDs and citations, 210 culinary-map paragraphs; zero paid calls. |
| Backend integration tests | Real lookup ambiguity, ambiance limits, scoped reviews, public-resource projections, constrained vector retrieval and PostgreSQL cache round trips. |
| Backend protocol tests | Discovery, connection reuse, invalid arguments, missing tools, prohibited mutations, path/SQL injection, unknown resources and unavailable trends over both transports. |
| Backend provider tests | Unknown/future/stale dates, citation-time freshness, timeout, cancellation, missing credentials, malformed responses, 429/5xx, bounded retry/backoff and `Retry-After`. |
| [Live smoke report](live_smoke_report.json) | Fresh local Tavily key, explicit enable flag, one news/basic request, one reported credit, two dated evidence items; three results excluded by freshness. |

Tavily queries contain only approved culinary concepts and broad geography. The
service permits two network attempts per application-issued run, including retries,
five results per request and a 30-second overall call deadline. Two configured
transient retries remain subordinate to that budget. Cache entries expire within
24 hours; evidence must also have a known publication date within 90 days and
cannot be future-dated. Cache reads and citation creation recheck freshness.
Unknown dates stay in stored provenance but cannot support current-trend claims.
Cache/provider failures return explicit unavailable outcomes without exception text.

The live report proves access and dated evidence availability. One result concerns
food-price trends, so dated results still require culinary relevance and claim
validation by the Phase 7 analyst. It does not establish ranking quality or endorse
any restaurant fact. Archived evidence expires; a stored report is not current
trend evidence indefinitely. The real catalog checks use sparse example queries
and do not establish user-photo generalization, dietary safety or a full agent demo.

From `backend/`, export the intended local database URL, mounted `MEDIA_ROOT`,
provisioned `MINILM_ROOT` and `CLIP_ROOT`. Run `make verify-mcp-catalog` for the
read-only wire-transport rehearsal. Run `make check` with the disposable
`TEST_DATABASE_URL` and provisioned test/pretrained model settings from the
[CI guide](../../infra/ci.md). Tests block external provider networking.

For a deliberately enabled live smoke, put a fresh Tavily key in the existing
root `.env`, preserve local configuration, then run:

```bash
ENABLE_LIVE_TAVILY=1 make smoke-food-trends
```

Process environment settings override the selected dotenv file. This command may
use up to two Tavily requests, persists public evidence in the intended database,
and writes the report; it makes no Groq call. Ordinary tests and health checks do
not call either paid provider. Do not use a test database to store live evidence.

Dependencies were kept locked (FastMCP 4.0.10, Tavily SDK 0.8.4; the adapter uses
bounded async HTTP), with JSON Schema validation explicitly pinned at 4.26.0.
Final backend `make check`: **388 tests passed without skips**, Ruff lint/format
and strict mypy passed. Relative documentation links, code fences, unique task IDs,
the 32 KiB instruction budget and the redacting source scan passed.

Version-specific behavior was checked against [FastMCP clients](https://gofastmcp.com/clients/client),
[tools](https://gofastmcp.com/servers/tools) and
[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search).
The existing Groq model configuration is preserved; model capability checks and
six-agent inference remain Phase 7. Original-history publication review, local
media recovery, 16 entity-review pairs and later application/release gates remain.
