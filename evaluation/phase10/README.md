# Phase 10 — Evaluation and hardening (P10-01–10)

Scope is P10-01 through P10-10. Later performance, full release and Langfuse
work remains unchecked. All acceptance providers are fake; no paid requests.

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
