# Portfolio demonstration (P11-06)

The [screenshot gallery](../evaluation/phase11/portfolio.md) records the
`foodwise-ai` presentation and administrator workflow. It uses synthetic prompts
and an isolated two-entity catalog. Next.js, FastAPI, PostgreSQL/pgvector, HTTP
MCP, MiniLM/CLIP retrieval and checkpoint persistence are real; extraction and
agent inference are controlled, live trends are unavailable, and Cloud tracing
is disabled. Every screenshot includes a capture annotation stating these
conditions. The annotation is added by the capture harness, not the product UI.

Use the separate [P11-04 live demonstration](live-demo.md) and its recorded
report when discussing OpenAI, all six real agent outcomes and dated Tavily
evidence. These portfolio screenshots do not demonstrate live-provider quality
or fulfill the original course screenshot submissions. The
[course requirement map](../evaluation/phase11/course-screenshots.md) preserves
the original filenames and expected views separately.

## Reproduce the capture

Install locked dependencies and Chromium, recover the validated original
`recipe1.png`, and provision the revision-pinned MiniLM/CLIP bundles as documented
in the [administrator rehearsal](admin-demo.md). Docker must be available;
localhost ports 3100 and 8119 must be free. The harness refuses to reuse servers,
does not read the owner's dotenv, and removes only its own disposable database,
volume and private media/work directory. No provider credentials are required.

Run from the repository root, choosing a new screenshot destination:

```bash
backend/.venv/bin/python infra/verify_admin_demo.py \
  --minilm-root .local-tmp/minilm \
  --clip-root .local-tmp/clip \
  --portfolio-dir .local-tmp/portfolio-recapture \
  --output .local-tmp/portfolio-recapture-report.json
```

Use `--pnpm /absolute/path/to/pnpm` and an already provisioned `COREPACK_HOME`
if required by the local tool installation. The verifier never installs packages,
downloads models or media, or calls paid providers. It runs the 21 existing
database/API contracts, builds the production frontend, and selects the opt-in
[portfolio journey](../frontend/tests/integration/portfolio.spec.ts). Normal
browser runs skip that journey. Omitting `--portfolio-dir` retains the P11-05
administrator demonstration.

Require `passed: true`, all database contracts executed with zero failures/skips,
one passed portfolio browser case, seven decoded metadata-free PNGs, matching
file hashes, and successful cleanup. The verifier exports only the seven named
images after browser success and database cleanup. It refuses to overwrite an
existing destination. Raw logs, browser traces, cookies, passwords, configuration
files and uploads are excluded from the export. DOM checks reject recognizable
credential/path text and password fields are masked. Review every final image
visually before using it; pattern checks alone cannot establish privacy.

## Presenter steps

1. Open `/` at 1440 × 1000. Introduce the English meal workspace, **Cook** and
   restaurant modes, examples and synthetic-catalog label. Capture `01-home.png`.
2. Choose **Cook**, send **Classic Margherita Pizza**, and expand **Sources**.
   Show the catalog citation excerpt and result limitations. Capture
   `02-text-citations.png`; refresh to demonstrate the retained conversation.
3. Expand **Edit preferences**, add **milk** as a hard allergen restriction,
   and send the same query. Show **No supported matches** and the retained
   explicit restriction. Capture `03-hard-restriction.png`. The earlier pizza
   card remains conversation history, not a new eligible suggestion. Delete
   this synthetic conversation before the next scene.
4. Switch to 390 × 844, choose **Cook**, upload the original recipe-1 pizza
   image, and send **Classic Margherita Pizza**. Show its actual associated
   catalog image and responsive result. Capture `04-image-mobile.png`, then
   delete the conversation/upload. The journey checks a numeric image score in
   persisted evidence; that score is retrieval relevance, not ingredient or
   allergen verification.
5. Return to desktop `/admin`, sign in with the disposable fixture password,
   choose **recipe**, and preview **Portfolio tomato basil rice. Italian.**
   Capture `05-admin-preview.png`. SQL inspection confirms the preview has
   created no recipe; the UI says that a separate save is required.
6. Enter rice, tomato and basil on separate ingredient lines and **Simmer rice
   with tomato and basil.** as the direction. Explicitly create, change the
   name to **Portfolio tomato basil rice edited**, and save version two.
   Capture `06-admin-saved.png` with the saved state visible.
7. Open the named delete dialog and capture `07-delete-confirmation.png`.
   Choose **Keep it** and verify version two remains. Reopen, confirm deletion,
   verify the row is absent, and sign out. The verifier checks that only the
   original restaurant/recipe and their two text/one image vectors remain.

Only synthetic browser content and catalog excerpts appear in the committed
captures. Original datasets/images, course notebooks/PDFs and owner configuration
remain local and ignored. This branch commit does not publish the gallery or
resolve the separate original-history/source review and complete-release gates.
