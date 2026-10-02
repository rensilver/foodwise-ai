# foodwise-ai frontend

The product name is **foodwise-ai**, with this exact spelling and casing.
[product.ts](src/lib/product.ts) exports `PRODUCT_NAME` for UI headings,
navigation labels, and browser/page metadata when those interfaces are
implemented. The private package in [package.json](package.json) uses the same
name. P01-05 adds a minimal English startup page, product metadata and
`/health/live`; recommendations and catalog interfaces remain planned.

The folders reserve the approved Next.js App Router layout. P01-02 pins Node
24.19.0 in the root [.nvmrc](../.nvmrc) and pnpm 12.8.1 in
[package.json](package.json). The manifest and [pnpm-lock.yaml](pnpm-lock.yaml)
lock Next.js 16.3.8, React 19.3.0, Tailwind CSS 4.3.3, TypeScript 5.9.3,
matching React/Node type definitions, and the Radix/utilities used by shadcn/ui.
The shadcn components themselves will be generated into the repository during
UI work. Node type definitions follow the runtime's major version (24).

Use Node 24.19.0 and pnpm 12.8.1. If using nvm, run `nvm install` and `nvm use`
at the repository root; install pnpm with `npm install --global pnpm@12.8.1`.
Then run from `frontend/`:

```bash
pnpm install --frozen-lockfile
pnpm exec next --version
pnpm exec tsc --version
```

[pnpm-workspace.yaml](pnpm-workspace.yaml) enforces runtime versions, exact new
dependency declarations, and compatible peers using the current
[pnpm settings format](https://pnpm.io/settings). It also retains pnpm's explicit
version exceptions for the resolved Node types and Lucide release-age checks.
pnpm 12 records its package-manager dependency in the first YAML document of
the lockfile and the application graph in the second.
Installation was verified on Linux x86_64. See the official
[Next.js installation guide](https://nextjs.org/docs/app/getting-started/installation)
and [pnpm installation guide](https://pnpm.io/installation) for tool setup.

P01-05 adds the strict TypeScript configuration required by the startup page,
and enables Next.js standalone output for the container. Shared quality scripts
remain P01-06. From `frontend/`, run `pnpm dev` for a localhost development
server or `pnpm build` for a production build. The
[Compose guide](../infra/README.md) starts the standalone production server
and documents health checks and synthetic-configuration verification.

| Location | Responsibility |
| --- | --- |
| `src/app` | Pages, layouts, and the same-origin API proxy. |
| `src/features/chat` | Conversation UI, follow-ups, progress, and image upload controls. |
| `src/features/preferences` | Explicit preferences and hard dietary constraint controls. |
| `src/features/recommendations` | Result cards, details, citations, and limitations. |
| `src/features/catalog` | Catalog browsing and administrator previews and CRUD forms. |
| `src/components` | Shared accessible presentation components. |
| `src/lib` | Generated OpenAPI types, API clients, and shared utilities. |
| `tests/components` | Component and accessibility tests. |
| `tests/e2e` | Playwright browser journeys. |

FastAPI owns application behavior. The frontend uses its API through a
same-origin proxy; generated contracts will come from OpenAPI in P08-10.
Provider secrets and database access stay on the server.

P01-04 adds [next.config.mjs](next.config.mjs), which rejects all
`NEXT_PUBLIC_*` variables during development and production configuration
loading. It also rejects the backend configuration names and both Compose
database password names, including
unprefixed values: client components can read those during server rendering
and expose them in HTML. The scaffold needs no public environment settings. The guard runs
after Next.js loads frontend dotenv files and never prints variable values.
It also leaves Next.js `env` empty: that option can expose values in browser
bundles even without a public prefix. See the official
[environment-variable guide](https://nextjs.org/docs/app/guides/environment-variables)
and [Next.js env option](https://nextjs.org/docs/app/api-reference/config/next-config-js/env).

Keep the root `.env` for the backend; do not copy it into the frontend, export
its settings into the frontend process or inject them into client code. Use
separate process environments for backend and frontend. Future proxy configuration
belongs on the Next.js server. If a public setting becomes necessary later,
add an explicit reviewed allowlist and tests before enabling it.

Run the offline configuration checks from `frontend/` after locked installation:

```bash
node --test tests/configuration.test.mjs
```

The tests use synthetic values, exercise Next.js configuration/dotenv loading,
and confirm that a build with backend canaries fails before rendering. A
temporary minimal application built with a clean environment then verifies
browser JavaScript and HTML contain no private canary. Temporary fixtures are deleted afterward; these
checks do not call external providers. The separate Compose smoke test boots
the committed startup application with synthetic configuration.
The Node test runner needs subprocess support. Shared quality scripts remain
P01-06, and full application bundle checks must be repeated as UI/proxy code
is implemented.
