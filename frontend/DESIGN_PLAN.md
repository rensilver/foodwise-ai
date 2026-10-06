# Phase 9 frontend design and delivery plan

Status: implemented and reviewed, 2026-10-05. This document defines the
[Phase 9](../CHECKLIST.md#phase-9--nextjs-frontend-and-administration) contracts.
See [recorded evidence](../evaluation/phase9/README.md) for verification and limits.
The subsequent [frontend redesign plan](REDESIGN_PLAN.md) proposes the
user-selected hybrid home, green-and-white palette and left sidebar; it retains
the behavior contracts below and does not replace historical verification.
The [frontend-design skill](../.agents/skills/frontend-design/SKILL.md)
informs the visual direction and review process. Existing API contracts and
[project rules](../AGENTS.md) govern behavior.

## Product brief

foodwise-ai helps a person decide where to eat or what to cook from a local
synthetic teaching catalog, then refine that choice through conversation.
The main audience is a nontechnical diner or home cook; catalog administration
is a separate, quieter workspace. English is the interface language.
Use `PRODUCT_NAME` from [product.ts](src/lib/product.ts) for branding and metadata.

The first screen should make a dinner decision possible immediately: “What
sounds good?” above “Eat out,” “Cook,” and “Both” category controls, a message
field, and an optional food image. Examples such as “Find Italian restaurants
in San Francisco” and “Help me choose a recipe with chickpeas” populate an
editable draft; they never send automatically. Show “Synthetic teaching catalog”
with a short explanation near the entry point and catalog results.

The memorable element is the meal-choice workspace: the same conversation can
produce two clearly separated groups, “Places to eat” and “Recipes to cook.”
Their layouts reflect the available evidence: restaurant rows foreground location,
cuisine and source price bands; recipes foreground ingredients, source time strings
and correctly associated imagery when available. Neither group borrows facts,
images or ranking positions from the other.

## Visual direction and tokens — P09-01

Use the crisp blue and white of a glazed serving dish, with a restrained yellow
selection accent. Keep most of the screen quiet so the meal choices carry the
personality. The following six colors define the initial light theme; verify
actual text, focus and control contrast in implementation before accepting it.

| Token     | Value     | Role                                                   |
| --------- | --------- | ------------------------------------------------------ |
| Porcelain | `#F5F8FC` | Page background                                        |
| Plate     | `#FFFFFF` | Composer, open dialogs and selected content surfaces   |
| Ink       | `#18283B` | Primary text                                           |
| Slate     | `#536579` | Supporting text and control outlines                   |
| Cobalt    | `#214CB5` | Primary actions, links and focus indicators            |
| Saffron   | `#F0C76A` | Selected category with Ink text; never a safety signal |

Use Bricolage Grotesque at weight 600 for the opening question and section
headings, and Source Sans 3 at 400/600 for reading, controls and source excerpts.
These are proposed assets: verify licenses, retain attribution, and self-host
the required Latin WOFF2 files during implementation. Build and page load must
work without a font CDN. Use `system-ui, sans-serif` fallbacks with reserved
layout space. Do not add a third face for metadata.

Use a restrained type scale of 14/16/20/25/32/40 px; body text and inputs start
at 16 px, with 1.5 line height. The opening question grows from 32 px on mobile
to 40 px on desktop; other headings remain smaller. Keep reading lines near
65 characters, below 80. Left-align headings, copy, forms and results; center
only compact control contents. Keep headings sentence case and a single color.

Use a 4/8/12/16/24/32/48 px spacing scale, a 1200 px maximum workspace, and
16 px mobile / 32 px desktop gutters. Give form controls a 6 px radius, the
composer and dialogs 12 px, and category selections a pill shape. Result rows
use spacing and semantic headings instead of identical floating tiles. Reserve
shadows for overlays; borders separate controls or related content. Use existing
Lucide icons alongside accessible labels. No decorative gradients, food emoji
wallpaper, stage numbers or dashboard statistics.

Interaction motion explains opening a panel, selection, or completion; avoid
autoplay imagery and repeated entrance animations. Respect reduced motion and
use static status text alongside any activity indicator. No dark theme is
required for this phase.

## Layout exploration and selected structure

Two directions were considered before selecting the workspace:

```text
A. Photo-led discovery               B. Meal-choice workspace (selected)
+------------------------------+    +--------------------------------------+
| Large food image / question  |    | foodwise-ai   Find a meal   Catalog   |
| Search                      |    | What sounds good?                    |
+------------------------------+    | [Eat out] [Cook] [Both]               |
| Recipe tiles | Place tiles  |    | Message + optional image + Send      |
+------------------------------+    | Places to eat     | Recipes to cook |
                                    +--------------------------------------+
```

A makes photography carry the identity, but the current restaurant dataset has
no reliable cover-image corpus and the task depends on follow-ups and evidence.
B makes choosing between eating out and cooking the main visual moment while
keeping the user's request and restrictions close to the results.

Selected desktop layout after a response:

```text
+---------------------------------------------------------------------+
| foodwise-ai     Find a meal     Catalog                Administration |
| Synthetic teaching catalog                                          |
+----------------------------------------------+----------------------+
| Current request and earlier messages         | Your preferences     |
| Activity or clarification                    | Must avoid           |
|                                              | Likes                |
| Places to eat         Recipes to cook        | Location / budget    |
| Name / source facts   Name / ingredients     | Edit preferences     |
| Why this fits         Why this fits          |                      |
| Sources / details     Sources / details      |                      |
|                                              |                      |
| Follow-up composer / image / Send or Stop    |                      |
+----------------------------------------------+----------------------+
```

Use the preference rail only when the result columns retain readable widths
(initial target: 1100 px and above). At intermediate widths, move preferences
to a disclosure and stack the result groups. On phones, use a single document
flow: navigation, category choice, preference summary/disclosure, conversation,
both result groups, composer. Do not hide one category behind a carousel or
make citation access hover-only.

```text
+--------------------------------+
| foodwise-ai              Menu  |
| What sounds good?              |
| [Eat out] [Cook] [Both]         |
| Preferences (summary)          |
| Request / activity / response  |
| Places to eat                  |
| Result / Sources / Details     |
| Recipes to cook                |
| Result / Sources / Details     |
| Message / Add image / Send     |
+--------------------------------+
```

Keep one main vertical scroll. A sticky composer is optional only if browser
tests show it never obscures focused content, results or the phone keyboard.
Maintain reading position during progress updates; offer “New response” when
the person has scrolled up instead of forcing a jump. Detail pages must support
direct navigation and return to the previous results and filters.

Proposed routes are `/` for starting a meal request, `/conversations/[id]` for
owned history, `/catalog/restaurants` and `/catalog/recipes` with `[id]` detail
pages, and `/admin` for sign-in and catalog management. These are UI routes;
backend endpoints remain under `/api/v1`. A known conversation URL can be
restored through the ownership-checked API. Do not assume an all-conversations
listing endpoint or introduce account navigation.

## Interaction and evidence contracts

| Tasks          | Planned behavior and acceptance                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| P09-02, P09-13 | Use generated types and a fixed server-side backend destination. Preserve cookie paths, status codes, CSRF/origin checks, SSE framing, heartbeats, run IDs and abort propagation. Test split stream chunks and post-header errors. No proxy buffering, cached private responses or automatic message POST retry. Langfuse stays server-side under the existing plan.                                                                                                                       |
| P09-03         | “Send” creates one intentional turn with a fresh `client_request_id`; prevent double submission and handle active-run `409`. Restore owned history on refresh. Separate “New conversation” from confirmed “Delete conversation”; deletion explains history/preferences/upload cleanup and handles active-run conflicts and `cleanup_pending`.                                                                                                                                              |
| P09-04         | Separate “Must avoid” from “Likes,” showing explicit and inferred values where supplied. Display active restrictions beside follow-ups. Send explicit additions/removals using the generated preference contract; omitting a field never means removing a restriction. Explain pending edits apply to the next message; use returned history as persisted truth. Contradictions invite clarification. Location and budget apply to restaurant requests only.                               |
| P09-05         | “Add image” has a keyboard-accessible file picker and visible JPEG/PNG/WebP, 10 MiB guidance. Show preview, upload state, server errors and “Remove image.” Prevent sending a pending/failed attachment. Removal detaches it from the draft; it does not claim server deletion. Revoke local object URLs; submit only the returned media ID. Never imply an image establishes ingredients or allergen absence.                                                                             |
| P09-06         | Map actual agent events to plain activity, such as “Finding options” and “Checking dietary evidence.” Represent parallel outcomes without a fictional sequential percentage. “Stop” aborts the stream; after a disconnect or cancellation, load history and report the confirmed state. No automatic inference replay. Keep draft text available for an explicit new request.                                                                                                              |
| P09-07         | Render at most five unique items per category from validated results. Show name, supported facts, explanation, relevant limitations, “Sources” and “View details.” Sources disclose excerpts, entity/document identity and available dates; distinguish publication and retrieval dates. Dietary unknowns are text, never a green approval badge. Do not present relevance as confidence or safety.                                                                                        |
| P09-08         | Browse with URL-backed search, supported category-specific filters and pagination. Retain filters on return from details. Recipe details use canonical ingredients/directions; restaurant details use available cuisine/location/price-band fields. Label dataset ratings and synthetic reviews. Unknown time, nutrition, hours or availability stays unknown.                                                                                                                             |
| P09-09         | Separate administrator sign-in from conversation ownership. Support logout/expiry; keep passwords and CSRF tokens out of persistent browser storage. Present extraction as “Preview fields,” followed by an editable review and separate “Create restaurant” or “Create recipe.” Editing uses “Save changes.” On version conflict, preserve the draft and offer the latest record for review, with no automatic overwrite. Confirm deletion with the record name and linked-review impact. |

Render untrusted text with escaped output or sanitized Markdown; disallow raw
HTML and unsafe link protocols. Citation links use descriptive names. Preserve
source strings and nulls instead of inventing friendlier but unsupported facts.

### States and interface copy — P09-10

| State                         | Visible response and recovery                                                                                                                                                    |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First visit                   | “What sounds good?” with editable examples and a working composer; no invented recommendations.                                                                                  |
| Pending                       | Announce actual activity politely without reading every heartbeat; keep Stop available and block duplicate Send.                                                                 |
| Clarification                 | Show the server question beside the reply field; preserve active restrictions and uploaded-image context.                                                                        |
| No supported matches          | Explain the returned evidence gap and offer editing the request; never suggest removing an allergy to fill results.                                                              |
| Trends unavailable            | “Current trend information is unavailable.” Keep otherwise valid recommendations and their sources visible.                                                                      |
| Partial analysis or imagery   | Show the relevant limitation near affected results. Use a compact “Image unavailable” area only where an image was expected; image-free restaurant rows should look intentional. |
| Upload rejected               | Name the server-reported problem and allow selecting another file without clearing the message.                                                                                  |
| Connection interrupted        | “Connection interrupted. Checking saved conversation.” Then show persisted completion or the confirmed incomplete state; sending again requires an explicit action.              |
| Request failed                | Explain the safe server error with an actionable retry/edit option; do not show stack traces or hide previous successful results.                                                |
| Admin expiry/conflict/failure | Preserve unsaved fields in memory, explain sign-in/review/retry, and show success only after server confirmation.                                                                |

## Contract gaps to resolve before image presentation

The current [generated contract](src/lib/api/generated.ts) exposes browser-owned
uploads through `/media/{id}`; `CatalogDetail` has no dedicated image receipt or
catalog-image URL. Do not assume filesystem paths, raw dataset URLs, citation IDs
or the review placeholder are browser-renderable catalog images.

P09-02/P09-05/P09-07 must first audit actual result media references and authorized
read behavior. If catalog image delivery is missing, record and implement the
narrow server contract needed for correctly associated catalog media, regenerate
OpenAPI types and verify access controls before completing those tasks. Report
that dependency explicitly; a missing-image layout alone does not satisfy the
image recommendation journey. Do not build a general URL fetcher or fabricate
image associations. Query upload/preview can proceed with existing contracts.

## Delivery order and verification gates

Keep the existing task IDs and use the following increments. Implementation uses
red/green/refactor tests for observable behavior; this planning change needs only
document checks.

| Increment                  | Tasks                          | Completion evidence                                                                                                                                                                            |
| -------------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Foundation                 | P09-01, P09-02, P09-12, P09-13 | Tokenized shell, route/feature boundaries, generated client/proxy and representative empty/result/error fixtures; verify cookies, streams, secret isolation and the media contract dependency. |
| One complete meal request  | P09-03, P09-06, P09-07         | Request → actual progress → cited response → follow-up → refresh; include clarification, stop, disconnect and no-replay tests.                                                                 |
| Preferences and images     | P09-04, P09-05                 | Retained restrictions and explicit corrections; valid and rejected uploads; media ownership and correct result-image identity.                                                                 |
| Catalog and administration | P09-08, P09-09                 | Browse/detail, login/logout/expiry, preview without persistence, create/edit/delete, conflict recovery and searchable committed changes.                                                       |
| Review and acceptance      | P09-10, P09-11                 | State matrix, keyboard/mobile journeys, visual critique and real API/database acceptance evidence.                                                                                             |

Use fixtures with real schema shapes and source-backed identities, including
long names/excerpts, null fields, both categories, no matches and missing images.
Fixtures belong in tests, not runtime fallback responses. Keep `app` as route
shells, `features` as behavior, `components` as shared UI, and `lib` as generated
contracts/clients. FastAPI retains culinary rules, ownership and mutation logic.

During implementation, run existing `pnpm check` and `pnpm test:e2e` from
`frontend/`. Extend component/browser coverage as needed rather than documenting
nonexistent commands. Add an automated accessibility check with a pinned tool
when implementing P09-10, alongside manual keyboard and screen-reader review.
Verify visible focus, dialog focus return, associated errors/labels, sensible
heading order, status announcements, 44 px primary touch targets, text contrast
of at least 4.5:1 and control/focus contrast of at least 3:1. Check 320, 390, 768
and 1440 px widths, 200% zoom, reduced motion and the mobile keyboard, with no
page overflow or obscured controls.

Capture screenshots of first use, both result categories, expanded sources,
strict-dietary no-match, interrupted run and administrator conflict at desktop
and phone widths. Review hierarchy, reading order, contrast, long-content wrapping
and image attribution; record what changed after critique. Store synthetic-only
review artifacts in an ignored local directory and record commands, outcomes and
artifact paths in Phase 9 evidence. Screenshots do not replace interaction tests.

Ordinary automated tests use fake OpenAI/Tavily boundaries. Separately exercise
the browser against the real FastAPI/PostgreSQL/MCP path with controlled provider
fixtures, verifying persistence, isolation and CRUD becoming searchable. These
checks establish integration, not live expert acceptance. Paid live runs remain
explicit opt-in, and the existing Phase 7/full-release live acceptance blocker
remains visible. Passing mock browser journeys alone cannot close Phase 9.

## Design review before implementation

The first concept paired a large food photograph with a uniform card grid.
Reviewing it against the data and conversational task exposed two problems:
restaurant imagery would be misleading, and identical cards would obscure the
difference between visiting a place and cooking a recipe. The selected plan
replaces that concept with the meal-choice workspace and category-specific facts.

The blue palette alone is not distinctive. The distinguishing choices are the
two dinner paths within one request, preferences remaining visible across
follow-ups, and inspectable sources attached to each choice. Keep the cobalt
category/composer area as the one strong visual emphasis; remove decorative
badges, extra borders and redundant labels during screenshot review. A reviewer
should recognize a food decision tool even with the wordmark hidden. If it reads
as a generic chat dashboard, revise hierarchy and real content before adding polish.
