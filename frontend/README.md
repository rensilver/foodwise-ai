# Frontend scaffold

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

Strict TypeScript configuration and quality scripts remain scheduled in
P01-06. Application pages and startup commands are pending.

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
