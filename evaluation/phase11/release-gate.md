# P11-08 — Complete local release gate

The local v1 capability gate passes on 2026-10-06 (America/Recife), against
revision `4744ea51d0ef7440ffbde988feac3f99f8761f74` and the refreshed
[acceptance report](../phase10/acceptance_report.json). The
[sanitized gate receipt](release_gate_report.json) binds the checked source,
locks, model files and prior release receipts to fresh acceptance results.
P11-09–12 remain separate tasks; the whole Phase 11 exit criterion is not marked
complete by this review.

| Required capability | Evidence supporting acceptance |
| --- | --- |
| Validated imagery | Fresh read-only decoding and hash comparison cover all 109 `recipe{id}.png` images and the recovered ZIP, with no missing, extra or duplicate identities/content. ZIP paths, member bounds, CRCs and original media hashes pass. P11-02/03 additionally verify nine decoded review images and their actual review/restaurant links. The unlinked placeholder supplies no evidence. |
| Real multimodal RAG | P11-01–04 use the complete 210-restaurant, 109-recipe, ten-review corpus with 770 MiniLM text and 118 CLIP image vectors. P11-04 issues actual pretrained CPU/pgvector queries through MCP: restaurant `1000088` and owned-image recipe `20` receive valid catalog citations and component scores. Fresh real API journeys verify CLIP image identity, private uploads and searchable CRUD. |
| Exactly six agents | Both positive P11-04 turns complete all six roles successfully. This review independently checks stage order, overlapping trend/style/nutrition execution and one synthesis after the join. The full offline suite exercises all-candidate analysis, failure joins, restrictions and output validation. |
| Live dated search | P11-04 records one fresh Tavily search and eligible cached evidence on the next turn. Actual web excerpts, publication dates, retrieval times, candidate associations and supported quotations pass independent receipt checks. Dated evidence is within the 90-day window and cache lifetime at that demonstration. Unavailable-trend fixtures are additional failure checks. |
| Frontend and administrator usability | Fresh production Chromium UI/accessibility journeys and seven real Next.js/FastAPI/PostgreSQL/checkpoint/HTTP MCP journeys cover text/image results, citations, preference corrections, refresh/cancellation/no replay, uploads, catalog navigation and both CRUD categories. P11-05 adds preview discard, cancelled deletion, validation/session recovery, optimistic conflicts and transactional cancellation contracts. |
| Passing acceptance | Full backend, frontend quality, browser and four-persona grounding acceptance pass. Every required configured database/model/browser scenario executes without skips. Persona fixtures return their labeled recommendation, abstention or clarification outcome with zero fabricated IDs/citations, hard-constraint violations or duplicates. |

Supporting receipts: [setup](clean_setup_report.json),
[persistence](persistence_report.json), [restore](backup_restore_report.json),
[live demonstration](live_demo_report.json), [administrator](admin_demo_report.json)
and [portfolio](portfolio_report.json). Their content hashes are recorded in
the gate receipt. Fresh checks also verify all 18 pinned model files and all
seven portfolio PNGs against their recorded hashes; the PNGs decode without
metadata. Historical receipts remain unchanged.

The live recommendation/MCP/retrieval/provider source is unchanged since commit
`671c8292851da66430c89233d64b00ea84a6e30b`. The only later backend runtime change
is administrator recipe-duration validation, independently covered by P11-05
and this full rerun. P11-04's runtime/verifier hashes match the current files.
The P11-05 verifier subsequently gained P11-06 portfolio capture; its current
hash matches P11-06 and its original application/test hashes still match.
Live evidence is reused from the same local date, with no new paid calls.

The first full backend run passed 620 tests and 64 subtests but failed the
existing acceptance-report hash contract: eight bindings still described the
pre-P11-04 implementation. Running the existing evaluator refreshed those
bindings and measurements without changing labels, source hashes, runtime,
expected outcomes or completion marks. The final complete rerun passes. This
correction preserves the drift contract rather than weakening its checks.

The first real API browser run passed six journeys but exposed a fixture defect
in the seventh: `providerCounts()` always read the old Phase 9 artifact path,
even when the server wrote counters into this run's private directory. That
made cancellation/no-replay assertions use unrelated stale data. Two red
regressions reproduce wrong-directory reads and unsafe fallback; the corrected
helper honors `FOODWISE_BROWSER_ARTIFACTS`, fails on a missing current receipt
and resolves relative roots from the backend fixture's working directory. Three
regressions and the final seven-journey run pass. Application cancellation code
and existing assertions are unchanged.

## Fresh acceptance results

| Check | Result |
| --- | --- |
| Backend Ruff lint/format, strict mypy and OpenAPI drift | Passed |
| Backend unit/contract/real PostgreSQL suite | 621 tests and 64 subtests passed; zero failures or skips |
| Four-persona graph report | Ten cases, twelve turns; expected outcomes match and all four violation counters are zero |
| Frontend generated contracts/format/lint/strict types | Passed |
| Frontend unit/component and configuration suites | 28 and five tests passed |
| Production UI/accessibility/browser assets | Ten journeys passed; zero skips |
| Real API/database/checkpoint/HTTP MCP/admin browser suite | Seven journeys passed; zero skips |
| Source and production browser credential scan | Zero findings |

The receipt's JUnit total includes the 64 subtests: 685 records correspond to
621 tests plus 64 subtests, not 685 independent pytest tests. Both configured
pretrained encoder contracts and both MCP transports execute in the backend
suite. Browser extraction/inference is controlled; real full-catalog live
inference remains the separate P11-04 evidence. No representative live-quality
or new performance measurement is inferred from these acceptance counts.

## Reproduce the acceptance checks

Follow the [isolated CI database procedure](../../infra/ci.md#reproduce-the-database-and-model-checks-locally)
to start a fresh localhost `foodwise_test` database and bootstrap its limited
role. Keep the owner's application database separate. Use the locked environment,
pre-provisioned offline model fixtures, pretrained MiniLM/CLIP bundles, recovered
recipe media and installed Chromium from the [setup guide](../../infra/release-setup.md).
From the repository root, set the existing test/model variables:

```bash
export TEST_MODEL_ROOT="$PWD/.local-tmp/test-models"
export TEST_MINILM_ROOT="$PWD/.local-tmp/minilm"
export TEST_CLIP_ROOT="$PWD/.local-tmp/clip"
export P09_MINILM_ROOT="$TEST_MINILM_ROOT"
export P09_CLIP_ROOT="$TEST_CLIP_ROOT"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.local-tmp/playwright"
export UV_CACHE_DIR="$PWD/.local-tmp/uv-cache"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 NEXT_TELEMETRY_DISABLED=1
```

After configuring `TEST_DATABASE_URL` and bootstrapping with
`TEST_DATABASE_ADMIN_URL` as documented in the CI guide, run from `backend/`:

```bash
uv run --locked ruff check --no-cache src tests scripts migrations
uv run --locked ruff format --check src tests scripts migrations
uv run --locked mypy
uv run --locked python scripts/export_openapi.py --check
uv run --locked python scripts/evaluate_phase10_acceptance.py
uv run --locked pytest -p pytest_asyncio.plugin -q
```

The recorded run uses the installed locked `.venv/bin` tools directly, which
avoids package-network access. Then run from `frontend/`, with pinned pnpm on
`PATH`:

```bash
pnpm check
pnpm exec playwright test --reporter=json
pnpm exec playwright test --config playwright.integration.config.ts --grep-invert 'P11-06 portfolio' --reporter=json
```

The excluded portfolio capture is opt-in P11-06 work; all seven normal real API
journeys execute. Run backend tests before the browser harness seeds its catalog;
use a new disposable database before repeating migration tests. The harness binds
localhost ports 3100/8119 and uses controlled inference/extraction, real CPU
models, persisted checkpoints and HTTP MCP. Remove only the disposable test
container/volumes and private generated browser media when finished. Finally,
from the repository root:

```bash
backend/.venv/bin/python scripts/scan_secrets.py --build-root frontend/.next
git diff --check
```

The separate [live procedure](../../infra/live-demo.md) remains explicitly opt-in;
offline browser inference cannot substitute for its successful live receipt.

## Remaining limits and release scope

The old provider rejection/degraded-expert records remain historical evidence.
P11-04 supplies the required successful six-role, fresh-search and persistent
follow-up capabilities. Broad live persona quality, user-photo generalization,
verified nutrition/allergen absence, sustained capacity and physical-device/spoken
assistive-technology coverage remain unmeasured. The catalog is synthetic, with
sparse demo history and 16 explicitly reported same-name/location pairs whose
source IDs remain preserved. Conservative unknown-dietary abstention is required
behavior, not a successful verified dietary match.

Clean checkouts still require owner-issued provider credentials and separately
restored ignored media; P11-01 rehearses that provisioning and P11-03 rehearses
same-version paired recovery. Publication/history review and course grading
screenshots remain separate. Public hosting and multi-user accounts are deferred.
Normal Langfuse conversation export remains disabled pending operational gates;
optional Cloud tasks P11-11/12 do not replace application acceptance.

This run reads no owner dotenv, issues no OpenAI/Tavily/Cloud calls, downloads no
models and changes no service configuration, dependency lock, catalog dataset or
course artifact. Disposable containers/volumes and generated private browser
media are removed; original container identities, start times and restart counts
are preserved. Local execution is the recorded evidence; a hosted CI result is
not claimed.
