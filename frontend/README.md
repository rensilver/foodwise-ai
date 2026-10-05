# foodwise-ai frontend

The English meal workspace implements chat, owned follow-ups, explicit preferences,
image drafts, cited recommendations, catalog browse/details and local administration.
Branding and metadata import `PRODUCT_NAME` from [product.ts](src/lib/product.ts).
The synthetic teaching catalog and unknown/degraded evidence are labeled explicitly.

Use the [design plan](DESIGN_PLAN.md) and [Phase 9 evidence](../evaluation/phase9/README.md)
for interaction contracts, visual critique and verification limits.

## Setup and local servers

Use Node **24.19.0** and pnpm **12.8.1**, locked in the root `.nvmrc` and manifest.
From `frontend/`:

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Run FastAPI separately following the [developer guide](../infra/development.md).
The same-origin `/api/v1` proxy defaults to `http://127.0.0.1:8000`.
`FOODWISE_API_ORIGIN` is a server-only setting accepting the fixed local hosts
`localhost`, `127.0.0.1` or Compose `backend`, without a path or credentials.
Compose supplies `http://backend:8000`. The browser always calls relative URLs.
Use matching allowed browser origins in backend configuration.

Keep the root `.env` in the backend process. Never copy it into `frontend/` or
export backend configuration into the Next.js process. The Next configuration
rejects all `NEXT_PUBLIC_*`, backend-only and `LANGFUSE_*`/`OTEL_*` configuration
without printing values. Langfuse integration remains backend scope in the
[Cloud plan](../infra/langfuse-plan.md); no telemetry SDK is a frontend dependency.
No provider, database or administrator credentials belong in browser code.
Cookies are forwarded with their separate Set-Cookie headers; administrator
CSRF tokens stay in memory and expire with the local grant. No localStorage
credentials or ownership IDs are used.

`pnpm build` creates standalone production output. The container and browser
startup script include `.next/static` and `public`, including local OFL font
assets. Tailwind v4 uses [postcss.config.mjs](postcss.config.mjs). Shared controls
use the installed Radix, CVA and Tailwind utilities following shadcn conventions.
Font attribution and licenses live in [public/fonts](public/fonts/README.md).

## Package boundaries

| Location                       | Responsibility                                                             |
| ------------------------------ | -------------------------------------------------------------------------- |
| `src/app`                      | Thin route shells, navigation/metadata, same-origin proxy and liveness.    |
| `src/features/chat`            | Owned history, editable drafts, POST SSE, recovery, activity and images.   |
| `src/features/preferences`     | Explicit additions/removals and hard/soft control presentation.            |
| `src/features/recommendations` | Category results, canonical facts, evidence and limitations.               |
| `src/features/catalog`         | URL-based browsing/details, admin session hook and typed forms.            |
| `src/components/ui`            | Shared buttons and accessible confirmation dialogs.                        |
| `src/lib`                      | Generated contracts, typed HTTP client, SSE framing and product/utilities. |

Route pages compose features; they do not perform application behavior. The
admin hook owns asynchronous session/catalog work; its workspace renders controls.
Features do not import route shells, shared components do not import features,
and library code does not import UI. Boundary tests enforce these dependencies.
FastAPI owns constraints, ranking, ownership, validation, embeddings, transactions
and version checks. Form conversion handles only primitive types and presentation;
there is no copied allergen dictionary, SQL, retrieval scoring or provider SDK.

Image results use entity-bound catalog receipts. Uploads use owned media IDs.
Sources are rendered as escaped React text with only validated HTTP(S) links;
raw HTML and Markdown execution are unsupported. There is no arbitrary URL fetch.

The POST stream reads incrementally with browser `fetch`, tracks conversation/run
identity and requires terminal `done`. On disconnect or Stop, it loads owned
history and preserves the draft. Refresh can restore an incomplete draft from
saved history. Sending again is always an explicit action with a fresh request
ID; refresh never replays inference. One active turn is enforced by both UI and API.

## Generated API contracts

[openapi.json](src/lib/api/openapi.json) comes from FastAPI and
[generated.ts](src/lib/api/generated.ts) from pinned `openapi-typescript`.
Do not edit these files manually or duplicate API schemas. After backend schema
changes, run `make api-schema` in `backend/`, then `pnpm api:generate` here.
`pnpm api:check` verifies drift. API client bodies/results and SSE events derive
from generated `paths` and `components`; TypeScript does not replace backend
runtime validation. See the [HTTP contract](../backend/README.md#phase-8-http-contract).

## Quality scripts (P01-06)

All commands run from `frontend/` after locked installation.

| Command                              | Check or action                                                                        |
| ------------------------------------ | -------------------------------------------------------------------------------------- |
| `pnpm check`                         | Contract drift, formatting, ESLint, strict TypeScript, units and configuration builds. |
| `pnpm format` / `pnpm format:check`  | Pinned Prettier; generated contracts and assets are excluded.                          |
| `pnpm lint:fix`                      | Apply ESLint fixes; recheck afterward.                                                 |
| `pnpm api:generate`                  | Regenerate contracts from the committed backend export.                                |
| `pnpm test:unit` / `pnpm test:watch` | Vitest and Testing Library behavior/boundary tests.                                    |
| `pnpm test:config`                   | Environment isolation including an isolated production build.                          |
| `pnpm test:e2e:install`              | Install the locked Chromium binaries once.                                             |
| `pnpm test:e2e` / `pnpm test:e2e:ui` | Production Chromium UI states, keyboard, axe and responsive review.                    |
| `pnpm test:e2e:integration`          | Real FastAPI/PostgreSQL/checkpoint/HTTP MCP journeys with controlled inference.        |

Normal checks and mocked browser tests require no backend, provider credentials
or model downloads. Real journeys require an isolated `foodwise_test` database,
restored recipe1 media and provisioned offline models; follow the
[reproduction instructions](../evaluation/phase9/README.md#reproduction).
Paid live acceptance is separate and opt-in. Do not run database suites concurrently.

Keep port `127.0.0.1:3100` free for browser tests (plus 8119 for real API fixtures).
Each suite builds `.next`, starts standalone production output and shuts it down;
run builds and browser suites sequentially. For limited RAM, reuse disk-backed
ignored browser/scratch storage:

```bash
mkdir -p ../.local-tmp/playwright ../.local-tmp/scratch
export PLAYWRIGHT_BROWSERS_PATH="$PWD/../.local-tmp/playwright"
export TMPDIR="$PWD/../.local-tmp/scratch"
pnpm test:e2e:install
pnpm test:e2e
```

The locked ESLint/Vitest/Playwright configuration is documented by the manifests.
Unreviewed dependency lifecycle scripts fail installation. Screenshots, logs,
traces, uploads and course media remain Git-ignored. View retained browser traces
with `pnpm exec playwright show-trace <trace.zip>`.
