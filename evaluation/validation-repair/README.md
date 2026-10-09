# Recommendation validation repair — 2026-10-09

## Incident and diagnosis

FoodWiseAI displayed `validation_failed` after requests for a Chinese recipe and
Italian restaurants in San Francisco. The saved final run retrieved 18 candidates;
profile, retrieval and nutrition completed, while style/trends were unavailable
and recommendation synthesis failed.

Owner-authorized, read-only replays of the saved context reproduced these errors:

| Stage | Observed response | Rejection |
| --- | --- | --- |
| Recommendation | Two HTTP 200, completed responses | `recommendations: tuple_type`; the field did not match the required JSON array |
| Recommendation | An array containing four recommendations | An explanation failed the verbatim citation-grounding check |
| Style | Ten selections with indices `[0,1,2,3,5,6,7,8,9,10]` for a ten-candidate batch | Missing index 4 and invalid index 10 |

These are reproduced failure modes, not recovered original response bodies: the
original run retained typed outcomes, not raw provider output. Six diagnostic
OpenAI requests reported 116,010 total tokens. The second diagnostic cached each
response during its repair invocation; those invocations were not independent
provider samples. No raw prompts, responses, credentials or profile data are
included in this report.

The recommendation node discarded Pydantic field errors in its catch-all repair
path. Shared structured generation replaced style coverage errors with generic
quotation guidance. Also, when style was unavailable, synthesis received no
prevalidated recommendation quotations despite having usable catalog citations.
Successful HTTP transport therefore did not imply a valid recommendation.
The exact reason for the original trend unavailability was not established.

## Repair

- [Recommendation synthesis](../../backend/src/food_recommender/agents/nodes/recommendation.py)
  now asks for an internal `recommendation_indices` array. The model ranks/selects
  indexed, verified catalog quotations; application code copies their entity IDs,
  explanations and citations into the unchanged public recommendation contract.
  The provider cannot author or alter recommendation text, references or limitations.
  Duplicate/out-of-range indices, non-integer indices, extra output fields and more
  than five selections in a category are rejected. One repair attempt receives
  sanitized schema field errors or precise selection constraints.
- [Style analysis](../../backend/src/food_recommender/agents/nodes/style.py)
  supplies explicit candidate/option indices. Coverage repairs list expected,
  missing, unexpected and duplicate indices; option repairs give the valid local
  indices. Indices reset for each batch, and every candidate is still assessed.
- [Structured generation](../../backend/src/food_recommender/agents/structured.py)
  preserves explicitly authored `GroundingError` instructions. Arbitrary validator
  exception messages are still replaced with generic guidance. Schema feedback
  excludes input values, exception messages and Pydantic error URLs.
- [Shared catalog quotations](../../backend/src/food_recommender/agents/catalog_quotes.py)
  let synthesis use verified source facts when a candidate has no valid style
  observation. Valid style quotations retain precedence. With no eligible,
  publishable evidence, synthesis returns an empty result with limitations without
  calling the model. Otherwise, generation failure remains a typed failure, with
  no automatic publication of a fallback choice.
- [Prompt version `phase11-v3`](../../backend/src/food_recommender/agents/prompts.py)
  defines the selection contract and explicit batch indices. Controlled graph and
  frontend inference fixtures were updated to the same internal contract.

Hard-constraint eligibility, unsafe-claim/instruction screening, entity/citation
validation, verbatim explanation checks, five-result/category limits, deadlines
and bounded repairs remain enforced before publication. The public API/schema,
configured model, provider schema strictness and six-role graph are unchanged.
Trend unavailability remains an explicitly reported degradation. Explanations are
short source quotations, not newly generated prose.

## Verification

Red/green verification first reproduced four failures, then passed 14 focused
tests. The final selection change produced seven failing tests before implementation;
**all 21 recommendation/style tests passed afterward**. These cover invalid indices
(including booleans/strings), duplicates, category limits, bounded repair, model
ordering, schema-error feedback, rejected provider-authored explanations, grounded
style precedence, unavailable style, and hard restrictions.

The all-unit/contract run identified an expected implementation-hash mismatch in
stored acceptance evidence. The [offline acceptance report](../phase10/acceptance_report.json)
was regenerated against the new runtime/prompt hashes: **10 cases / 12 turns**,
zero fabricated IDs/citations, restriction violations or duplicate recommendations,
and zero paid provider calls. Original labels, source hashes and phase completion
marks were preserved. The acceptance report's timing values describe this fixture
run, not live model latency.

**470 unit/contract tests and 64 subtests passed** in 24.61 seconds. One optional
pretrained-model fixture check was skipped because `TEST_MODEL_ROOT` was unset;
retrieval/embeddings were not changed. Database integration and browser journeys
were not rerun for this agent-contract repair. Ruff lint and format checks passed
across 323 files; strict mypy passed across 174 source modules; OpenAPI drift passed.
The initial broader sandbox test attempt stalled with stream-descriptor errors and
was interrupted; completed broad runs used approved execution outside that sandbox.
This does not constitute a new full release acceptance run.

Reproduce from `backend/` using the existing locked environment:

```sh
.venv/bin/python scripts/evaluate_phase10_acceptance.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -p pytest_asyncio.plugin tests/unit tests/contract -q -rs
.venv/bin/ruff check src tests scripts migrations
.venv/bin/ruff format --check src tests scripts migrations
.venv/bin/mypy
.venv/bin/python scripts/export_openapi.py --check
```

## Runtime verification

An intermediate live replay with better feedback and source quotations, but still
freeform recommendation generation, assessed all **18 style candidates** successfully
while synthesis still failed after two attempts. It used five OpenAI calls and
96,768 reported tokens in 51.01 seconds. This evidence motivated the final indexed
selection contract instead of relying only on prompt/repair improvements.

The final backend image and bounded synthesis replay are being verified. Results
will be recorded here before handoff.
