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
and admin preview/create/edit/conflict/delete with searchable committed changes.
They inspect real document/vector rows rather than relying only on UI notices.

See [visual-review.md](visual-review.md) for critique, corrections and accessibility
limits. Synthetic screenshots and logs remain under `.local-tmp/phase9/` and
`frontend/test-results/`, ignored by Git. No physical mobile keyboard or spoken
screen-reader device was available; keyboard, accessible-tree, focus and automated
checks are the recorded evidence, not universal accessibility certification.

Real API verification on 2026-10-05: **4 browser journeys passed (56.2 s)**;
**18 unit/component tests passed** and strict TypeScript passed. Final combined
quality results are recorded below after the package and telemetry checks.

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
Run backend database tests and this harness sequentially, because their migration
fixtures intentionally create/drop application tables. Stop the disposable
container after testing. Full model/data recovery and release rehearsal remain
Phase 11 scope.
