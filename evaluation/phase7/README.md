# Phase 7 verification

This report records the original, pre-migration provider runs. Its JSON artifacts
retain the original model/provider identifiers and measurements; they are not
OpenAI verification. Current OpenAI results are tracked in
[the migration report](../openai-migration/README.md).

The six real role implementations, owned graph runner and deterministic rules are
implemented and tested. Each checklist task has a dedicated branch commit.

| Evidence | Result |
| --- | --- |
| Offline graph/role contracts | Actual expert overlap and one synthesis after the barrier; all 40 candidates reach expert analysis; malformed JSON, invalid IDs/citations, insufficient evidence and unavailable branches are tested. |
| Real PostgreSQL checkpoint/lease contracts | Restart continuity, retained follow-up restrictions/history, wrong-session rejection, cross-adapter active-run exclusion, cancellation and explicit new-turn behavior. |
| [Historical provider capabilities](legacy_provider_capabilities.json) | Explicitly enabled text and vision structured requests on the then-configured model; no model/provider fallback. The final vision fixture requires a red/green/blue/unknown label and correctly identifies a solid red image. An earlier unconstrained color probe did not match the expected label; the narrowed schema probe passed. |
| [Offline real-catalog graph](offline_catalog_graph_report.json) | Real stdio MCP/pgvector retrieval and checkpoints, with fake inference and Tavily disabled: 16 candidates, five cited results, one retrieval attempt, 7.677 seconds, zero paid requests. Style/trend are explicitly unavailable in this fixture. |
| [Full graph live smoke](live_graph_report.json) | Executed with explicit owner approval on 2026-10-04: all six stages, 16 real recipes, five dated Tavily sources and a completed checkpoint. Failed synthesis validation; zero recommendations. |
| [Live smoke diagnostics](live_graph_diagnostics.json) | A second graph run reproduced six HTTP 413 token-limit/request-size rejections. A minimal request using the style schema succeeded. Combined usage and cleanup checks are recorded. |

The offline real-catalog verification uses `tests/unit/test_agent_acceptance.py`
fixtures injected into the prepared smoke workflow. Its `passed` flag verifies
retrieval/graph/reference/checkpoint integration with fake inference, and does not
claim live OpenAI/Tavily completion. The live smoke task has now been executed;
the Phase 7 live acceptance gate remains open because the live run failed.

The full backend check passed 434 tests without skips after the package review.
The final trend relevance change passed 27 affected checks. Ruff/format/mypy,
document checks and redacting secret checks passed.
Offline tests use fake OpenAI/Tavily boundaries, a disposable PostgreSQL 16.14 /
pgvector 0.8.6 service, and provisioned CPU MiniLM/CLIP fixtures. They make no paid
provider requests. Capability requests are recorded separately above.

The live graph command uses a known Italian tomato/basil seed query, a new empty
conversation and no reviews/uploads. MCP runs in a separate stdio process over
real pgvector retrieval. Search concepts sent to Tavily come from its fixed public
allowlist. OpenAI receives the synthetic course recipe ingredients/catalog excerpts.
The script cleans its temporary conversation, session and checkpoint after recording
an outcome; catalog rows remain unchanged. On this machine the verified local
catalog snapshot was restored into an isolated smoke database and 770 text vectors
were built with the pinned MiniLM weights. The existing application on port 5432
was not modified. Source artifacts and the original snapshot were preserved.

With explicit external data transfer approval, run from `backend/` with local
service settings (database, media root and provisioned model paths):

```bash
ENABLE_LIVE_OPENAI=1 make check-openai-capabilities
ENABLE_LIVE_GRAPH=1 make smoke-agent-graph GRAPH_SERVICE_ENV_FILE=/absolute/path/to/private-services.env
```

The commands read the owner's selected local fresh keys; they never print them.
The full run is bounded to 120 seconds, 30 seconds/call, three concurrent OpenAI
calls, two transient retries, two schema repairs and one synthesis repair.
Retrieval permits three attempts; live trends permit at most two searches.
Reports record stage timing, call/token/search usage, candidate/citation IDs and
actual outcomes. Unavailable or irrelevant trends cannot become claims.

## P07-14 historical live outcome

The owner explicitly approved paid calls and sending synthetic course recipe
ingredients/catalog excerpts to the previous provider and public culinary concepts to Tavily.
Both graph runs used the configured model recorded in the JSON artifacts without model/provider
fallback. The first run took 17.325 seconds, retrieved 16 Italian recipes in one
attempt, and made eight requests to the previous provider plus one Tavily network search. Tavily
returned five sources with publication dates inside the 90-day window. The
style and trend outcomes were unavailable; nutrition retained deterministic
unknown assessments with structured-analysis limitations. Synthesis returned
`validation_failed`, with no recommendations. The completed checkpoint records
the terminal failure; it does not indicate successful recommendations. The
reference subset check is vacuously true for an empty result and provides no
live citation-validation acceptance evidence.

The diagnostic run took 8.967 seconds and reused the eligible trend cache,
making eight requests to the previous provider and zero Tavily network searches. It recorded HTTP
413 for style, both nutrition batches, trend inference and both synthesis
attempts. The rejected requests were 23,754–69,220 bytes; fixed error markers
identify token-limit/request-size rejection. A separate minimal style-schema
request returned HTTP 200 and the expected empty assessments array, supporting
request size as the blocker rather than an unsupported style schema.
The historical diagnostics identify provider token budgets; they do not establish
OpenAI limits, the owner's current allowance or a tier upgrade.

Across both runs and the diagnostic schema probe there were 17 requests to the previous provider
and 1,052 provider-reported tokens from five successful HTTP responses. Rejected
requests had no reported token usage. There was one Tavily network search;
credits were not exposed by the graph contract and remain unknown. Raw provider
errors, organization identifiers, prompts and credentials were not recorded.
Post-run SQL checks found zero temporary sessions, conversations or checkpoint
rows and unchanged catalog/vector counts: 210 restaurants, 109 recipes, 770
text embeddings. The opt-in guard and package boundary checks passed all 11
tests; Markdown/checklist and redacting source checks passed.

P07-14 is checked off because its requested smoke execution, outcome, limits and
usage are recorded. **The Phase 7 live acceptance gate remains open.** The next
fix must make complete expert/synthesis inputs fit the configured provider's
token limits without truncating canonical dietary ingredients, omitting
candidates, changing the model silently or exceeding the 120-second run budget.

This is integration evidence, not a quality evaluation. Explanations/style
observations currently quote source excerpts for deterministic grounding; they
are deliberately more limited than free prose. Nutrition quantities and
cross-contact safety remain unknown. Full persona evaluation, application
HTTP/SSE endpoints, frontend/admin journeys and public hosting remain later or
deferred scope.
