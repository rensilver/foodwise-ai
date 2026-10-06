# foodwise-ai frontend redesign plan

Status: planned, 2026-10-06 (America/Recife). No implementation is completed by
this document. User-selected direction: **hybrid meal request and recipe
discovery**, with **soft green and white adapted to foodwise-ai** and a left
sidebar inspired by the supplied Cookmate reference.

This is a focused design iteration on the verified application. Preserve the
[Phase 9 behavior contracts](DESIGN_PLAN.md) and its completion evidence.
The newer [P11-08 local release gate](../evaluation/phase11/release-gate.md)
records passing local v1 capabilities; older Phase 9 notes about live acceptance
are historical. Remaining Phase 11 and public-release work is separate.

## Review findings

Reviewed route shells, global CSS, shared controls, chat/preferences, catalog
browse/detail/admin, recommendation/source presentation, generated API types,
tests, and the existing [home and result screenshots](../evaluation/phase11/portfolio.md).
This is a source and recorded-screenshot review, not a fresh browser audit.

| Current implementation                                                                                                                           | Design consequence                                                                          | Planned improvement                                                                            |
| ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| [Root layout](src/app/layout.tsx) uses a small horizontal navigation bar.                                                                        | Recipes are reached through a generic Catalog link; there is no persistent left navigation. | Add direct meal, recipe and restaurant navigation with active states and a contextual sidebar. |
| [Meal workspace](src/features/chat/meal-workspace.tsx) places examples, actions and category controls above a large composer.                    | The first screen is mostly controls, with no food discovery.                                | Put a compact request area directly beneath the heading and a real recipe preview below it.    |
| [Preferences](src/features/preferences/preferences-panel.tsx) occupy a right rail only at wide sizes.                                            | Preferences compete with two result columns and precede results in mobile flow.             | Move them into the left sidebar; use a concise always-visible restriction summary on phones.   |
| [Catalog browser](src/features/catalog/catalog-browser.tsx) renders full-width forms and long result rows.                                       | Images and names are difficult to scan as a collection.                                     | Move filters into the sidebar and introduce a responsive recipe grid.                          |
| [Catalog facts](src/features/recommendations/catalog-presentation.tsx) always include the full recipe ingredient list, even in summary views.    | Cards become detail pages; comparing several meals requires considerable scrolling.         | Separate summary facts from full details and expandable ingredients.                           |
| [Recommendations](src/features/recommendations/recommendations.tsx) always reserve two desktop columns, even when only one category has results. | A recipe-only response wastes available width.                                              | Use full-width category sections, with recipe cards and compact restaurant rows.               |
| [Global CSS](src/app/globals.css) shares broad classes across forms and results.                                                                 | Uniform outlined surfaces flatten hierarchy and make page-specific changes risky.           | Add semantic tokens, scoped layout styles and purpose-specific shared controls.                |

The existing self-hosted fonts, typed API client, verified image associations,
source disclosures, ownership checks and cancellation behavior are strong
foundations to retain. No framework replacement or new UI dependency is needed.

## Visual direction

Use the reference's quiet sidebar, light surfaces, green selection treatment
and generous food images. The memorable element is the recipe imagery beside a
clear choice between cooking and eating out. Keep surrounding interface chrome
restrained. Continue to import `PRODUCT_NAME`; all product text remains English.

| Core token | Value     | Use                                   |
| ---------- | --------- | ------------------------------------- |
| Canvas     | `#F4F8F5` | Page background                       |
| Surface    | `#FFFFFF` | Cards, inputs, header and dialogs     |
| Ink        | `#20382C` | Headings and primary text             |
| Muted      | `#52665B` | Supporting text                       |
| Herb       | `#23734D` | Primary actions, links and focus      |
| Mint       | `#E2F1E7` | Selected navigation and soft emphasis |

Derive quiet separators from Ink at low opacity; essential input boundaries
must have independently verified contrast. Retain distinct error/warning colors
for semantic feedback. Mint never means a dish is safe for an allergy.
Use semantic CSS names such as `action`, `surface` and `text-muted`, replacing
color-specific component references such as `bg-cobalt` during implementation.

Retain **Bricolage Grotesque 600** for headings and **Source Sans 3 400/600** for
body and controls. These licensed local assets already distinguish the product;
new font downloads add no value here. Use 14/16/20/25/32/40 px type, 1.5 body
line-height, and 65–75 character reading widths. Align headings, copy, cards and
forms to the left. Use sentence case, with no decorative uppercase labels.

Use 4/8/12/16/24/32/48 px spacing. Target a 64 px desktop header, a 256 px sidebar,
24–32 px content gutters and an approximately 1440 px overall layout cap.
Use 8 px control corners, 12 px image/card corners and 16 px dialogs. Reserve
pill shapes for selections and tags. Shadows belong primarily to overlays;
food cards need only subtle boundaries. Motion explains user actions and obeys
reduced-motion preferences.

### Layout comparison and critique

```text
A. Discovery first                  B. Hybrid (user-selected)
Header / catalog search             Header / catalog search
Sidebar | Title + large grid        Sidebar | Meal request
        | More collections                  | Recipe preview grid
        | Assistant link                    | Restaurant browse link
```

A closely follows the screenshot but makes conversation and eating out harder
to discover. B keeps the reference's food-first scanning while expressing this
project's actual purpose: choose, inspect evidence, then refine the same meal
request. This is the selected implementation direction.

The first sketch could easily become a generic recipe marketplace. Revise it
by giving the request area equal priority, using distinct restaurant rows, and
keeping evidence available on every recommendation. Remove repeated collections
such as “Trending” and “Quick weeknight dinners” until their selection criteria
exist. Real recipe imagery carries the visual identity; avoid decorative hero
images, dashboard metrics and extra card wrappers around every section.

## Desktop and mobile structure

```text
+-----------------------------------------------------------------------+
| foodwise-ai           [Recipes v] [Search by name                 ]    |
+------------------+----------------------------------------------------+
| Find a meal      | What sounds good?                                  |
| Recipes          | [Eat out] [Cook] [Both]                            |
| Restaurants      | [Describe your meal...                            ] |
|                  | [Add image]                              [Send]    |
| Your preferences | Try: Italian in San Francisco / Chickpea recipe    |
| Must avoid       |                                                    |
| Likes            | Explore recipes                         Browse all |
| Edit preferences | Catalog browsing; preferences aren't applied here  |
|                  | [Actual photo] [Actual photo] [Actual photo]       |
| New conversation | [Name / facts] [Name / facts] [Name / facts]        |
|                  |                                                    |
| Administration   | Prefer eating out? Browse restaurants              |
+------------------+----------------------------------------------------+
```

After a message, the main area prioritizes conversation, activity, separate
recommendation categories and the follow-up composer. Remove the discovery
preview from that active conversation view. Keep `/` and `/conversations/[id]`
and the existing conversation lifecycle. Starting a new conversation restores
discovery. Preserve draft and pending-preference behavior through this change.

Sidebar content is contextual:

- Always: Find a meal, Recipes, Restaurants; Administration has lower emphasis.
  Use real links, icons with text, and `aria-current` for the active destination.
- Meal workspace: retained hard restrictions, soft preferences, edit controls
  and new-conversation action. Deletion remains a distinct confirmed action.
- Recipe catalog: name search and cuisine filter; selected filters and reset.
- Restaurant catalog: name, cuisine, location and maximum source price band.
- Details: category navigation and return to results with original filters.
- Admin: catalog-management context, without conversational preference controls.

Reuse the sidebar frame across views, but inject feature-owned content. Do not
make shared shell components import chat or catalog features. Never conflate
catalog filters with saved conversation preferences. A catalog reset must not
remove dietary restrictions. Pending edits still apply on the next explicit send.

At approximately 1120 px and above, show the 256 px rail and three recipe
columns where available width permits. Below that, replace the rail with a
named Menu/Filters/Preferences drawer; use two recipe columns when cards retain
about 260 px width. Phones use one column, 16 px gutters and a compact header.
Use available content width, not the device label, to decide the column count.

```text
+----------------------------------+
| Menu   foodwise-ai       Search   |
| What sounds good?                |
| [Eat out] [Cook] [Both]           |
| Must avoid: milk   [Preferences] |
| [Describe your meal...         ] |
| [Add image]               [Send] |
| Explore recipes       Browse all |
| [Photo                         ] |
| Name / source time / cuisine     |
| [Next recipe                   ] |
+----------------------------------+
```

Use one main page scroll; a tall sidebar/drawer may scroll for reachable
controls. A sticky desktop sidebar must not clip controls on short screens.
The mobile drawer traps focus, closes on Escape and restores trigger focus;
closed contents are not tabbable. Keep a single mounted preference editor so
resizing does not discard draft inputs. Avoid a fixed mobile composer in this
iteration; keep keyboard and focus targets unobscured.

## Features adapted to actual capabilities

| Reference idea                                   | Implementation for this project                                                                                                                                                               |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Global search                                    | Category selector plus “Search recipes by name” or “Search restaurants by name”; submit to existing catalog routes using `q`. Ingredient intent belongs in the meal request.                  |
| Cuisine chips                                    | Short, curated shortcuts using verified catalog cuisine values, with a labeled text input for other cuisines. The API accepts one cuisine, so use single selection. No invented facet counts. |
| Diet/lifestyle sidebar                           | Conversation preferences using existing explicit update/removal contracts. Keep hard requirements separate from soft likes. Dietary catalog filtering is unavailable.                         |
| “For you”                                        | Use only for completed personalized recommendations, if desired. Initial home content is “Explore recipes,” drawn from the real catalog and explicitly unfiltered by personal restrictions.   |
| Cooking time                                     | Display source time, with deterministic formatting of supported duration strings and raw-value fallback. No cooking-time range filter in this scope.                                          |
| Difficulty, verified health tags, recipe ratings | Omit: data/contracts do not support those claims. Restaurant ratings remain attributed dataset facts, preferably on details.                                                                  |
| Trending tags                                    | Show dated evidence only through the existing recommendation flow; no permanent trend section or extra search on page load.                                                                   |
| Save, share, profile, user login                 | Omit from this iteration. Persistent favorites/accounts are separate product work; local administrator sign-in remains available.                                                             |

The current catalog GET filters are `q`, `cuisine`, `limit`, `offset`, plus
restaurant-only `location` and `price_band`. Repository search matches names;
ordering is by entity ID. Do not label the first page “best,” “popular” or
“recent.” Do not filter one loaded page client-side and imply whole-catalog
results. This plan requires no API schema change or frontend dietary rules.

### Home, cards and details

- Fetch one bounded recipe preview, initially six items, from the existing API.
  It must not block the composer or trigger inference. Loading, empty and failed
  discovery states each retain a working meal request and catalog link.
- Use recipe cards with a reserved 4:3 image area, name, cuisine, source time,
  servings when useful, and a clear details link. Names wrap naturally. Use
  distinct skeletons and an intentional missing-image state.
- Preserve `CatalogImage`'s entity-bound authorized URL and failure behavior.
  Add responsive sizing and lazy loading for below-fold images. Keep provenance
  accessible with human-readable wording; machine IDs belong in source details.
  Detail images use their natural aspect ratio without forced cropping.
- Restaurant rows emphasize name, cuisine, location, source price band and
  explanation. Use only genuinely linked imagery when available; do not borrow
  recipe photos or generate supposed restaurant photos.
- Recommendation cards add “Why this fits,” visible dietary evidence/critical
  limitations, and Sources/Ingredients disclosures. Keep the complete canonical
  ingredients and citations accessible. No generated explanation is silently
  truncated; long content may use an explicit expand control.
- Consolidate exact repeated limitation text for presentation while preserving
  meaning and candidate association. Keep failed-analysis states visible.
  Earlier recommendations remain clearly attached to their original turn.
- Detail pages use a photo and summary area, then ingredients/directions or
  restaurant facts, and complete provenance. Extend the validated `returnTo`
  destinations to support home discovery without accepting arbitrary URLs.
- Admin receives the same typography, controls and spacing, plus clearer
  sections for finding, editing, previewing and saving. Preserve separate
  preview/save, unsaved drafts, conflict recovery and deletion confirmation.

## Implementation sequence

Every item below is planned. These are new redesign tasks, not reopened Phase 9
completion marks. Keep each delivery slice reviewable and passing its affected
tests. Use red/green tests for new interactions and observable behavior fixes.

| Order                                  | Files and work                                                                                                                                                                                          | Completion evidence                                                                                                                                                                     |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R01 — Baseline and visual foundation   | Record current screenshots; add semantic tokens in `src/app/globals.css`, update `src/components/ui/button.tsx`, and introduce narrowly scoped layout styles.                                           | Existing behavior passes; proposed color pairs and rendered focus/control contrast checked; desktop and phone comparison.                                                               |
| R02 — Shared shell and sidebar         | Add `src/components/layout/` presentation components; integrate through `src/app/layout.tsx` and feature views. Add drawer using existing Radix primitives.                                             | Active navigation, direct URLs, keyboard/Escape/focus return, short-screen overflow and responsive reflow verified.                                                                     |
| R03 — Catalog grid and filters         | Update `src/features/catalog/catalog-browser.tsx`; add catalog summary/card components and split summary/detail facts. Move supported filters into contextual sidebar.                                  | URL/back/forward/pagination preservation, category-specific filters, reset, loading/error/empty state, image fallback and no stale-result flash.                                        |
| R04 — Hybrid home and preferences      | Update `src/features/chat/meal-workspace.tsx` and `src/features/preferences/preferences-panel.tsx`; add catalog discovery feature using generated types. Keep `use-conversation.ts` as lifecycle owner. | Discovery failure leaves chat usable; preview makes no inference calls; examples remain editable; switching viewport preserves pending preferences; active/history views stay distinct. |
| R05 — Results, detail and admin polish | Update recommendation/source presentation, `catalog-detail.tsx`, `admin-workspace.tsx` and editor layout. Reuse card summaries without duplicating backend rules.                                       | Both/single-category layouts, full ingredients/citations, retained restrictions, safe return links, admin preview/save/conflict/delete verified.                                        |
| R06 — Acceptance and evidence          | Extend existing component and browser journeys; capture and critique the implemented screens; record results in a new redesign evidence document.                                                       | Quality checks and real API journeys pass; before/after screenshots reviewed; gaps and measured limits documented.                                                                      |

Keep `app` as route shells, `features` as behavior, `components` as reusable
presentation and `lib` as contracts/utilities. A small duration formatter can
live in `lib`; it must not invent minutes for unrecognized strings. No new
global state library is needed. Use the current generated client and preserve
same-origin cookies, media ownership, SSE run IDs, aborts and no-replay behavior.

## Validation and completion criteria

Planned commands from `frontend/`, after implementation:

```bash
pnpm check
pnpm test:e2e
pnpm test:e2e:integration
```

The integration command needs the documented disposable database, media/models
and fixture setup in [Phase 9 evidence](../evaluation/phase9/README.md); never
substitute the owner's database. Ordinary validation uses controlled providers.
Do not add paid calls or downloads just to validate this redesign.

Capture home, both catalogs, recipe detail, restaurant detail, both-category and
single-category responses, pending/empty/error/degraded states, mobile drawer,
preferences and admin conflict/deletion. Review 320, 390, 768, 1024 and 1440 px,
short laptop height, 200% zoom/reflow and reduced motion. Include keyboard and
axe checks, touch targets of at least 44 px, labeled controls, loading/status
announcements, no horizontal overflow and no obscured focus.

The redesign is complete when the first desktop view exposes the request and
the start of real recipe discovery, catalog cards are easy to compare, sidebar
controls do exactly what their labels promise, and all existing critical flows
retain their evidence. Measure image requests/layout shift and compare with the
baseline rather than claiming an unmeasured performance improvement.

Preserve historical portfolio captures and release receipts; save new screenshots
separately and document their revision. Add new completion evidence to
[CHECKLIST.md](../CHECKLIST.md) after verification. This planning document alone
does not close any implementation task or change prior release evidence.
