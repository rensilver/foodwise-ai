# Phase 4 text retrieval baseline — 2026-10-03

Phase 4 uses PostgreSQL 16.14/pgvector 0.8.6 over the verified synthetic seed:
**210 restaurants, 109 recipes and 10 reviews**. The final index has **770 normalized
384-dimensional MiniLM vectors**, including token-bounded culinary projections and
118 caption projections, plus the 118 original attributed captions. Source
projections retain hashes and character offsets. Canonical ingredients stay complete.

[The labeled queries](text_queries.json) contain 17 cases: restaurant ambiance and
signature queries, recipe ingredient/preparation queries, scoped synthetic review
retrieval, mixed category routing, impossible filters/IDs, and a strict-allergy
abstention. Each positive has an original source identity, exact supporting excerpt
and source hash. Labels are sparse selected positives, not exhaustive relevance
judgments. Unlabeled entities receive zero gain. Empty cases have null relevance
metrics and are checked as abstention outcomes.

[The measured report](baseline_report.json) records every query's ranked IDs,
component scores, supporting document IDs, model/source revisions, versions,
hardware, process memory and timings. It precedes agent reasoning and multimodal
ranking changes. Rankings reproduced exactly on the second request for every query.

| Metric | Initial result |
| --- | --- |
| Mean Recall@20 across labeled query/category pairs | 1.000 |
| Mean binary nDCG@5 across labeled query/category pairs | 0.967 |
| Mean cuisine diversity@5 (distinct known cuisines / returned items) | 0.603 |
| Warm median / p95 / maximum retrieval time | 38.75 / 122.79 / 125.57 ms |
| Offline CPU model loading time | 5.51 seconds |
| Evaluation process peak RSS | 569.79 MiB |
| Fabricated entities/citations, constraint/scope violations, duplicates | 0 |
| Groq calls, provider tokens, trend searches | 0 |

Relevance averages cover 15 positive query/category pairs; timings cover all 17
queries. Diversity excludes empty lists and treats unknown cuisine as no diversity
gain. Timings include query encoding, SQL, evidence construction and fusion, and
exclude the report's separate citation audit; they are warm, sequential requests
on localhost, not an HTTP or agent benchmark. CPU: AMD Ryzen 5 7520U, eight logical
CPUs, about 6.54 GiB RAM, single-thread CPU inference. This small labeled set does
not establish broad recommendation quality or allergen safety.

The real pinned encoder is `sentence-transformers/all-MiniLM-L6-v2` revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, CPU-only, with offline loading and a
local file-hash manifest. Random CI fixtures were used only for deterministic
adapter contracts. Indexing generated 770 vectors; a corrected caption-provenance
refresh replaced only 118 derived captions. The final full-corpus rerun returned
**770 unchanged, zero embedded**. No original catalog IDs, versions, source records,
media or owner configuration changed. Exact cosine and English full-text branches
share metadata/source filters; RRF uses equal branch weights and `k=60`, with entity
ranks deduplicated before fusion. Categories normalize separately and ties use IDs.

Every returned citation was checked against its actual document, source record,
source and entity link in PostgreSQL. Review citations must also match the requested
demo profile. Strict restrictions reject conflicting/unknown evidence before
ranking; this catalog lacks verified allergen absence, so the allergy case abstains.
Incomplete, absent or incompatible indexes return explicit dependency errors.

Verification: backend `make check` passed **325 tests, no skips**,
including real PostgreSQL and optional pretrained CPU contracts, plus Ruff
lint/format and strict mypy. Source scan, Markdown checks and `git diff --check`
passed. No paid provider requests occurred. PostgreSQL/process checks used the
repository's required execution permissions outside the restricted process sandbox.

To reproduce, restore the local Phase 3 media/corpus, follow the
[seed setup](../../backend/README.md#seed-ingestion-phase-3), explicitly select a
seeded database, and use the
[Phase 4 commands](../../backend/README.md#multi-source-text-retrieval-phase-4)
from `backend/`:

```bash
make provision-minilm
make index-text
make evaluate-text
make index-text
```

Set `DATABASE_URL` and `MINILM_ROOT` first; model provisioning is an explicit public
network download, while indexing/search/evaluation need only local files and
PostgreSQL. Tests use `TEST_DATABASE_URL`, `TEST_MODEL_ROOT`, and optionally
`TEST_MINILM_ROOT`, following the [CI reproduction guide](../../infra/ci.md).
The recorded evaluation used a disposable copy of the existing verified seed;
the original `foodwise_seed` database remained untouched. Model weights, database
dumps and private media remain ignored. The disposable evaluation container was
removed after checks; committed JSON retains reproducible evidence.

The 16 reported same-name/location identity groups and original-history publication
review remain unresolved. MCP tools, image retrieval, six-agent reasoning, live
trends and frontend acceptance remain later phases; Phase 4 does not satisfy the
full application release gate.
