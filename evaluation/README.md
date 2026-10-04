# Evaluation artifacts

The [Phase 0 report](phase0/README.md) and manifests preserve the verified source
and media baseline. [Phase 3](phase3/README.md) records seed acceptance;
[Phase 4](phase4/README.md) supplies source-backed text labels and measured retrieval
metrics before agent reasoning or multimodal ranking.

The scaffold also reserves:

- `queries/` for versioned text/image queries, personas, and follow-up cases.
- `fixtures/` for labeled entity IDs and supporting source evidence.
- `reports/` for measured retrieval, grounding, constraint, latency, and usage results.

These three folders contain placeholders. Populate them during the retrieval
baseline and evaluation phases, recording dataset and model revisions with each
report. Course instructions remain architectural references and never enter the
runtime culinary knowledge base.

[Phase 5](phase5/README.md) adds frozen multimodal labels, real image association
checks and five measured text/image fusion settings, with explicit scope limits.

[Phase 6](phase6/README.md) records real MCP transports and dated Tavily evidence.
[Phase 7](phase7/README.md) records graph/checkpoint verification and opt-in Groq
capabilities, with the executed live graph's Groq token-limit blocker stated explicitly.
[Phase 8](phase8/README.md) records HTTP/SSE, private media, admin transactions,
package/migration boundaries and generated frontend-contract verification.
