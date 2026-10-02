# Frontend scaffold

The folders reserve the approved Next.js App Router layout. `package.json`
contains project identity only. Node/pnpm pins, framework dependencies, and the
lockfile are scheduled in P01-02; strict TypeScript and quality commands are
scheduled in P01-06. Application pages and startup commands are pending.

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
