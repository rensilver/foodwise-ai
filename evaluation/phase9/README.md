# Phase 9 frontend evidence

Implementation on `feature/phase9-nextjs-frontend`, verified on 2026-10-05.
Each P09 task has a dedicated commit. This report distinguishes mocked UI state
checks from the real API/database/MCP journeys. Existing live Phase 7/full-release
acceptance remains separate; no paid OpenAI, Tavily or Langfuse requests occur.

## Runtime behavior

The English meal workspace uses the approved blue/white/yellow tokens and local
OFL fonts. App Router routes cover `/`, owned `/conversations/[id]`, category
browse/detail and `/admin`. Navigation and metadata import `PRODUCT_NAME`.

The same-origin proxy forwards cookies, CSRF/origin and request IDs to one fixed
local backend, keeps SSE unbuffered and propagates cancellation. Catalog image
receipts expose only IDs/dimensions; the narrow image endpoint validates actual
entity association, excludes private uploads and sanitizes bytes before delivery.
No filesystem path or arbitrary remote fetch reaches the browser.

Examples populate editable drafts. Owned history restores on refresh; an
incomplete request restores its text, category, pending edits and media context
for explicit resubmission. There is no POST retry/replay. New conversations and
confirmed deletion are separate actions. Actual six-agent activity is displayed
without percentages; Stop cancels upstream inference and the database lease.
Hard restrictions remain distinct from likes, and removals use explicit keys.

Uploads use media IDs, visible validation/pending/failed states and revoked blob
URLs. Removing a draft attachment does not claim server deletion. Results and
catalog details display canonical category-specific facts and actual linked
images. Expandable sources identify entity/record/document, attribution and
available publication/retrieval dates. React escapes untrusted text; unsafe
citation URLs are never linked. Unknown dietary compliance is text, not approval.

Administrator sessions/CSRF stay in memory and HttpOnly cookies. Preview has a
separate save action. Typed forms support create/edit and named deletion with
linked-review impact. Expiry and version conflicts preserve the draft; adopting
a newer version requires explicit review. Search uses committed retrieval rows.

## Verification layers

- `pnpm check`: generated contract drift, ESLint, strict TypeScript,
  component/unit behavior and configuration/security builds.
- `pnpm test:e2e`: production Chromium with intercepted schema-shaped API
  fixtures; first use, two categories, sources, unknown/empty/clarification/error,
  failed imagery, unavailable trends, interruption and admin recovery. Axe 4.11.0
  scans WCAG A/AA states without exclusions; keyboard and responsive screenshots
  cover 320/390/768/1440 px, reduced motion and 200% equivalent reflow.
- `pnpm test:e2e:integration`: production browser and proxy against real FastAPI,
  limited-role PostgreSQL/pgvector, PostgreSQL checkpoints, six LangGraph roles,
  HTTP MCP and locally provisioned pretrained MiniLM/CLIP. Controlled structured
  inference and unavailable live trends are explicit test boundaries. Socket
  guards prohibit external network access. This is separate from mocked UI tests.

The isolated harness serves distinct API/MCP ASGI applications in one test
process, with real HTTP round trips. The application's independent production
MCP process and both existing transport suites remain unchanged. This harness
establishes integration, not separate-process performance or live-provider quality.

Real journeys verify SQL persistence and ownership, cited text results, refresh
without more provider calls, retained restrictions and explicit removal, rejected
and valid uploads, genuine CLIP image scores and correct recipe1 image delivery,
private media isolation/deletion, actual cancellation, clarification and no-replay,
and recipe/restaurant admin preview/create/edit/conflict/delete with searchable
committed changes, catalog filters/pagination and return URLs.
They inspect real document/vector rows rather than relying only on UI notices.

See [visual-review.md](visual-review.md) for critique, corrections and accessibility
limits. Synthetic screenshots and logs remain under `.local-tmp/phase9/` and
`frontend/test-results/`, ignored by Git. No physical mobile keyboard or spoken
screen-reader device was available; keyboard, accessible-tree, focus and automated
checks are the recorded evidence, not universal accessibility certification.

Real API verification on 2026-10-05: **4 browser journeys passed (56.2 s)**;
**18 unit/component tests passed** and strict TypeScript passed. Final combined
quality results are recorded below after the package and telemetry checks.

Package review (P09-12): administrator operations are separated into a focused
hook, route shells compose features, generated contracts are excluded from manual
formatting, and import checks prevent provider/database/telemetry SDK dependencies
in presentation code. Standalone packaging carries PostCSS and public font assets;
Compose configures only the internal API origin for the frontend. Formatting,
lint, strict TypeScript, **22 unit/component tests**, **5 configuration checks**
and **9 responsive/accessibility browser tests (56.7 s)** passed after refactoring.

## Reproduction

Use the locked Node/pnpm/Python environment. Ordinary frontend checks need no
backend, credentials or models. Browser binaries must already be installed.

```bash
cd frontend
pnpm check
pnpm test:e2e
```

For real journeys, initialize an isolated localhost database named
`foodwise_test` using the [CI guide](../../infra/ci.md#reproduce-the-database-and-model-checks-locally).
Never use the owner's application database. Restore
`data/synthetic_recipe_images/recipe1.png` from the validated course archive, and
provision the existing offline models before running. From the repository root:

```bash
export TEST_DATABASE_URL='postgresql://foodwise_test_app:synthetic-ci-application-password@127.0.0.1:55439/foodwise_test'
export UV_CACHE_DIR="$PWD/.local-tmp/uv-cache"
export P09_MINILM_ROOT="$PWD/.local-tmp/minilm"
export P09_CLIP_ROOT="$PWD/.local-tmp/clip"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.local-tmp/playwright"
export TMPDIR="$PWD/.local-tmp/scratch"
cd frontend
pnpm test:e2e:integration
```

The harness refuses other database names/hosts, runs migrations/checkpoint setup,
seeds original recipe/restaurant identities using ingestion adapters and indexes
the matching recipe1 image. It binds only `127.0.0.1:8119`; the frontend binds
`127.0.0.1:3100`. The fixture administrator password is test-only and never used
by production. Fixture data/media remain in the isolated test environment.
Run backend database tests before seeding this harness, using a fresh disposable
service. Their migration/downgrade fixtures expect an empty application schema;
recreate the test service before rerunning them after browser journeys. Never
reset the owner’s database. The first combined rerun demonstrated these fixture
collisions; a clean disposable service resolves the setup issue. Stop the disposable
container after testing. Full model/data recovery and release rehearsal remain
Phase 11 scope.

## Final verification — P09-13

On 2026-10-05 the final combined checks passed:

| Check | Result |
| --- | --- |
| Frontend contracts/format/lint/strict types | Passed |
| Vitest component/unit/boundary contracts | 25 passed |
| Configuration/dotenv/isolated build contracts | 5 passed |
| Production UI/accessibility/browser-asset journeys | 10 passed, 46.1 s |
| Real API/database/checkpoint/HTTP MCP journeys | 5 passed, 58.0 s |
| Backend Ruff/format/mypy/OpenAPI contracts | Passed |
| Full backend unit/contract/PostgreSQL suite | 475 passed, 69.31 s; no skips |
| Redacting source scan | 0 findings |

Versions: Python 3.12.14, Node 24.19.0, pnpm 12.8.1, Next.js 16.3.8,
Playwright 1.63.0 and axe 4.11.0 on Linux. Both pretrained retrieval integration
checks were enabled; the harness uses restored original recipe1 media and a
small seeded catalog. These are acceptance fixtures, not large-corpus quality or
hardware/latency benchmarks.

The proxy keeps the backend's response request ID and SSE conversation/run IDs.
The browser test passively clones the same POST response for inspection; it
verifies all six domain-role progress events, one correlated terminal completion
and matching persisted assistant run IDs. Unit tests reject mixed identities and
cover typed post-header errors. Stop and disconnect abort actual fixture inference;
intentional cancellation closes the local stream without an AbortError stack.
Upstream failures remain failures; no POST is retried automatically.

Next configuration rejects all `LANGFUSE_*` and `OTEL_*` settings, including
arbitrary aliases, before rendering. Synthetic canary configuration tests verify
values are not printed. Import/dependency checks exclude telemetry SDKs from the
frontend, and a test scans the actual production JavaScript/HTML assets. Follow
[the Cloud plan](../../infra/langfuse-plan.md) for the later backend integration;
this phase introduces no telemetry UI, API fields, Cloud account or external calls.

| Task | Concrete evidence |
| --- | --- |
| P09-01 | Route shells, local licensed fonts, tokens and four-width keyboard/axe views. |
| P09-02 | Proxy cookie/CSRF/error/abort contracts, generated drift and entity-scoped image tests. |
| P09-03 | Real owned history, editable prompts, clarification, duplicate-turn guard and confirmed deletion. |
| P09-04 | Real saved restrictions, follow-up retention and explicit removal; pending-edit component checks. |
| P09-05 | Real rejected/valid uploads, preview/draft states, media ownership and matching image delivery. |
| P09-06 | Six-role activity, actual cancellation, persisted recovery and refresh without more inference. |
| P09-07 | Separate canonical categories, expandable citations/dates and unknown/degraded evidence. |
| P09-08 | Real filters, pagination, detail return URLs and category-specific fields. |
| P09-09 | Real preview without persistence, both CRUD categories, vectors, conflict recovery and deletion. |
| P09-10 | Responsive/zoom/reduced-motion, focus/keyboard/axe states and recorded visual corrections. |
| P09-11 | Five real browser/API/PostgreSQL/checkpoint/MCP journeys, separately from mocked UI tests. |
| P09-12 | Import-boundary tests, thin shells, admin behavior hook, generated clients and standalone assets. |
| P09-13 | Request/run correlation, SSE/error/cancellation and browser telemetry credential/SDK isolation. |

Each task has its own branch commit; inspect `git log --reverse --grep=P09-`.
The checklist preserves all other phases' completion marks and release blockers.
No branch push, public hosting, production database reset or owner configuration
change was performed.
