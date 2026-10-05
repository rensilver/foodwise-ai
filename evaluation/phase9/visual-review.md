# Phase 9 visual and accessibility review

Reviewed on 2026-10-05 using production Chromium, self-hosted fonts and controlled
synthetic API fixtures. Screenshots are local, ignored artifacts in
`.local-tmp/phase9/mock-screenshots/`; browser tests reproduce them in
`frontend/test-results/`.

The reviewed desktop and 390 px result screenshots clearly separate places to
eat from recipes to cook. Restaurant facts remain image-free; the intentionally
failed recipe image shows its limitation and actual entity association. Sources
stay alongside the relevant result. Desktop preferences occupy a reading rail;
mobile preferences precede conversation results. One vertical scroll keeps the
composer from covering focus targets. Palette and fonts match DESIGN_PLAN.md.

Corrections from review:

- Axe found `aria-label` on a generic response anchor. Give the anchor a region
  role; keyboard jumping moves focus there without automatic scrolling.
- Tailwind's reset removed heading/list margins and bullets, crowding source
  facts and ingredients. Restore a measured reading rhythm, visible bullets and
  smaller preference headings. Recheck screenshots after this correction.
- Constrain Next build workers to two for the project's limited-memory host.
- Mock restaurant citation record IDs now match the restaurant fixture instead
  of carrying a copied recipe record identity.

State checks include empty dietary evidence, clarification, errors, interrupted
streams, missing images, unavailable trends, admin conflicts and expired sessions.
Axe 4.11.0 runs WCAG 2/2.1 A/AA rules without exclusions. Keyboard checks cover
skip navigation and dialog Escape/focus return. Accessibility-tree inspection
checks named landmarks, labels, disclosure controls and live status semantics.
Widths are 320, 390, 768 and 1440 px with reduced motion; a 720 px CSS viewport
checks reflow equivalent to 200% zoom at 1440 px. These are desktop Chromium and
emulated mobile checks, not physical-device or spoken assistive-technology tests.
They do not establish universal accessibility conformance.

After correction, `pnpm check` passed generated drift, ESLint, strict TypeScript,
17 component/unit tests and five configuration/security tests. `pnpm test:e2e`
passed nine production browser tests, with zero reported axe violations in all
scanned states. Corrected screenshots retain both groups and expanded sources at
all four widths, plus desktop/phone admin conflicts and strict-empty/interrupted
states. Heading separation and list markers make source facts easier to scan.
