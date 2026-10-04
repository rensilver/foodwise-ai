# Phase 7 verification

The six real role implementations, owned graph runner and deterministic rules are
implemented and tested. Each checklist task has a dedicated branch commit.

| Evidence | Result |
| --- | --- |
| Offline graph/role contracts | Actual expert overlap and one synthesis after the barrier; all 40 candidates reach expert analysis; malformed JSON, invalid IDs/citations, insufficient evidence and unavailable branches are tested. |
| Real PostgreSQL checkpoint/lease contracts | Restart continuity, retained follow-up restrictions/history, wrong-session rejection, cross-adapter active-run exclusion, cancellation and explicit new-turn behavior. |
| [Groq capabilities](groq_capabilities.json) | Explicitly enabled text and vision structured requests on configured `qwen/qwen3.8-27b`; no model/provider fallback. The final vision fixture requires a red/green/blue/unknown label and correctly identifies a solid red image. An earlier unconstrained color probe did not match the expected label; the narrowed schema probe passed. |
| [Offline real-catalog graph](offline_catalog_graph_report.json) | Real stdio MCP/pgvector retrieval and checkpoints, with fake inference and Tavily disabled: 16 candidates, five cited results, one retrieval attempt, 7.677 seconds, zero paid requests. Style/trend are explicitly unavailable in this fixture. |
| [Full graph live smoke status](live_graph_report.json) | Prepared, but execution awaits specific approval for sending catalog evidence to Groq. Automatic approval review rejected the attempted execution; no catalog data was sent by that attempt. |

The offline real-catalog verification uses `tests/unit/test_agent_acceptance.py`
fixtures injected into the prepared smoke workflow. Its `passed` flag verifies
retrieval/graph/reference/checkpoint integration with fake inference, and does not
claim live Groq/Tavily completion. The separate live status remains blocked.

The full backend check passed 434 tests without skips after the package review.
The final trend relevance change passed 27 affected checks. Ruff/format/mypy,
document checks and redacting secret checks passed.
Offline tests use fake Groq/Tavily boundaries, a disposable PostgreSQL 16.14 /
pgvector 0.8.6 service, and provisioned CPU MiniLM/CLIP fixtures. They make no paid
provider requests. Capability requests are recorded separately above.

The live graph command uses a known Italian tomato/basil seed query, a new empty
conversation and no reviews/uploads. MCP runs in a separate stdio process over
real pgvector retrieval. Search concepts sent to Tavily come from its fixed public
allowlist. Groq receives the synthetic course recipe ingredients/catalog excerpts.
The script cleans its temporary conversation, session and checkpoint after recording
an outcome; catalog rows remain unchanged. On this machine the verified local
catalog snapshot was restored into an isolated smoke database and 770 text vectors
were built with the pinned MiniLM weights. The existing application on port 5432
was not modified. Source artifacts and the original snapshot were preserved.

After external data transfer approval, run from `backend/` with explicit local
service settings (database, media root and provisioned model paths):

```bash
ENABLE_LIVE_GROQ=1 make check-groq-capabilities
ENABLE_LIVE_GRAPH=1 make smoke-agent-graph GRAPH_SERVICE_ENV_FILE=/absolute/path/to/private-services.env
```

The commands read the owner's selected local fresh keys; they never print them.
The full run is bounded to 120 seconds, 30 seconds/call, three concurrent Groq
calls, two transient retries, two schema repairs and one synthesis repair.
Retrieval permits three attempts; live trends permit at most two searches.
Reports record stage timing, call/token/search usage, candidate/citation IDs and
actual outcomes. Unavailable or irrelevant trends cannot become claims.

This is integration evidence, not a quality evaluation. Explanations/style
observations currently quote source excerpts for deterministic grounding; they
are deliberately more limited than free prose. Nutrition quantities and
cross-contact safety remain unknown. Full persona evaluation, application
HTTP/SSE endpoints, frontend/admin journeys and public hosting remain later or
deferred scope.
