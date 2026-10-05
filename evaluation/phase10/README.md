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
