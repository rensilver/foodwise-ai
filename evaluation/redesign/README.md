# FoodWiseAI redesign acceptance

R01–R06 are complete, verified on 2026-10-07 (America/Recife), against
`db2318a` plus the final branding/control fixes. This report closes the
[redesign plan](../../frontend/REDESIGN_PLAN.md), preserving historical Phase 9
and Phase 11 evidence. Machine-readable results are in [verification.json](verification.json).

## Delivered work

| Task | Implementation and acceptance |
| --- | --- |
| R01 | Herb/mint semantic tokens and shared controls (`5456be1`); responsive screenshots and axe contrast checks pass. |
| R02 | Navigation, contextual sidebar and responsive drawer (`00290fd`); active destinations, focus containment/Escape/return and draft retention pass. |
| R03 | Recipe grid, summary facts and category filters (`5f6a4a3`); URL/history/pagination/reset, empty states and image fallback pass. |
| R04 | Compact meal request, catalog discovery and sidebar preferences (`c4f9f91`); discovery outage leaves chat usable, pending restrictions survive reflow, and real follow-ups persist. |
| R05 | Evidence cards, details and admin presentation (`814329f`); citations, image associations, return URLs, preview/save/conflict/delete and cancellation pass. |
| R06 | Final screenshots, 17 production browser checks, eight real integration journeys and this acceptance report. |

The requested final adjustments use `FoodWiseAI` through `PRODUCT_NAME` in the
header and page metadata. Repository/package identifiers remain `foodwise-ai`.
Dropdowns use a 16 px chevron inset 12 px from the right and centered vertically,
with space reserved for the option text. Forced-colors mode restores the native
arrow. Radio/checkbox inputs no longer inherit the 8 px top margin intended for
stacked text fields. The meal choices retain native radio semantics.

## Verification

| Check | Result |
| --- | --- |
| `pnpm check` | Contract drift, formatting, ESLint and TypeScript passed; 42 unit/component tests and five configuration tests passed. |
| `pnpm test:e2e` | Production build and 17 Chromium journeys passed, 1.1 minutes, one worker. |
| Real integration suite | Eight journeys passed in 50.1 seconds, including the opt-in portfolio journey. |
| Final capture measurements | Header/title `FoodWiseAI`; radio/text center difference 0 px; dropdown position `calc(100% - 12px) 50%`; no horizontal overflow at 320, 390 or 1440 px. |

Browser acceptance covers 320/390/768/1024/1440 px, short-height drawer reflow,
200% equivalent reflow, reduced motion, keyboard navigation and axe WCAG A/AA
checks. It includes pending, empty, clarification, error, unavailable trends,
image failure, admin conflict/expiry and discovery failure states.

Real journeys used a separate limited-role PostgreSQL/pgvector database,
FastAPI, checkpoints, HTTP MCP and local pretrained MiniLM/CLIP. Inference was
controlled and trend unavailability explicit. Tests verified persistent
preferences, cited recommendations, owned uploads and linked image delivery,
cancel/no-replay behavior, searchable CRUD and catalog navigation. No paid
provider calls, model downloads or owner-database writes occurred.

The interrupted run before the user's memory report had no completed quality
receipt. It is not counted as passing. Fresh checks ran sequentially in systemd
scopes capped at 1600 MiB for quality, 1800 MiB for production browser checks,
and 2300 MiB for real integration, with at most 128 MiB additional swap per
scope. The disposable database had a separate 256 MiB cap. Vitest now defaults
to one worker. These changes bound validation concurrency; the original freeze's
cause was not established. All temporary servers and the test database were
removed after verification.

Reproduce with the locked tools and commands in the
[plan](../../frontend/REDESIGN_PLAN.md#validation-and-completion-criteria) and
[real API setup](../phase9/README.md#reproduction). For this constrained-machine
run, integration reused the exact production build from `pnpm test:e2e`:
a temporary Playwright config retained the integration server/test settings and
replaced only its frontend build/start command with `node scripts/start-e2e.mjs`.
`FOODWISE_PORTFOLIO_DIR` enabled the eighth journey. Logs and temporary configs
remain locally under `.local-tmp/redesign/`; they are ignored by Git.

## Screenshots and critique

Fresh production captures are separate from the original redesign screenshots:

- [Desktop home](screenshots/2026-10-07/home-1440.png)
- [Mobile home](screenshots/2026-10-07/home-390.png)
- [Narrow mobile with Restaurants selected](screenshots/2026-10-07/header-restaurants-320.png)
- [Preferences drawer](screenshots/2026-10-07/drawer-390.png)
- [Results and source disclosures](screenshots/2026-10-07/results-sources-1440.png)
- [Admin conflict recovery](screenshots/2026-10-07/admin-conflict-390.png)

The header has clear spacing around its chevron and the longest category name
fits on mobile. Radio indicators and labels now share a center line. At 320 px,
meal choices wrap without overlap. At 1440×900, the request and the start of
recipe discovery are both visible. Home captures intercept catalog responses
using original linked course images; labels identify that boundary. The
`real-api-*.png` captures in the same directory come from the separate real API
portfolio journey with controlled inference. Historical screenshots are intact.

The [raw capture metrics](screenshots/2026-10-07/visual-metrics.json) retain the
same six image responses and 14,106,719 image bytes as the prior local capture.
First recipe position remains 741.5 px at 1440 width and 1023.89 px at 390 width.
Desktop layout-shift entries total about 0.799, matching the preceding capture;
mobile entries total about 0.107 versus the preceding capture's 0.008. These are
single local fixture loads with different timing, not field Core Web Vitals or
evidence of a performance improvement. Image payload reduction and loading
stability remain possible future optimizations, outside the requested control
polish. Physical-device and spoken screen-reader testing were unavailable.

No required redesign implementation or acceptance item remains open. Public
hosting, unrelated release work and performance optimization are not closed by
this report.
