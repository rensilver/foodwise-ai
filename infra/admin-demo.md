# Administrator demonstration (P11-05)

Run from the repository root after installing the locked backend/frontend
dependencies and Chromium. Restore the original
`data/synthetic_recipe_images/recipe1.png` from the validated course archive,
and provision the revision-pinned MiniLM/CLIP bundles using the
[setup guide](release-setup.md). Docker and the pinned Node/pnpm/Python tools
must be available. Ports `127.0.0.1:3100` and `127.0.0.1:8119` must be free;
the browser harness refuses to reuse an existing server.

```bash
backend/.venv/bin/python infra/verify_admin_demo.py \
  --minilm-root .local-tmp/minilm \
  --clip-root .local-tmp/clip \
  --output evaluation/phase11/admin_demo_report.json
```

Use `--pnpm /absolute/path/to/pnpm` if pnpm is outside `PATH`. An existing
Corepack cache can be selected with `COREPACK_HOME`; provision it beforehand.
The verifier never installs dependencies or downloads models. Browser binaries
are expected under `.local-tmp/playwright`, as in the
[frontend integration guide](../evaluation/phase9/README.md#reproduction).

The command creates an independently named PostgreSQL/pgvector container with
a random localhost port, new database administrator password, and the limited
`foodwise_test_app` test role. It runs database contracts before the browser
harness applies migrations/checkpoint setup and seeds an original restaurant,
recipe and associated image. It builds and starts the production Next.js app,
real FastAPI and HTTP MCP retrieval using pretrained CPU encoders. Structured
inference/extraction responses are controlled and external Python sockets are
blocked. No owner dotenv or application database is read; provider calls and
Cloud tracing are absent.

The browser demonstration runs four journeys covering both categories:

1. Sign in, preview extracted fields, verify no database write, discard the
   preview with **New entry**, then preview again and explicitly create.
2. Inspect committed document/vector rows; open the named delete confirmation,
   choose **Keep it**, and separately close it with Escape. Neither sends DELETE.
3. Submit invalid recipe duration or oversized restaurant signature text. A real
   HTTP 422 preserves the draft and prior catalog/document/vector snapshot.
   Correct the input, revoke the server session, and verify sign-in recovery
   preserves the draft before explicitly saving version two.
4. Retrieve the edited entity through the actual six-agent/API/MCP flow. Require
   its lexical and dense ranks and a validated recommendation. Confirm deletion,
   verify detail returns 404 and retrieval no longer recommends its identity,
   then delete the synthetic conversation and sign out.
5. In the existing recipe journey, use a second authorized browser to create an
   actual optimistic version conflict. The first browser retains its draft,
   reviews version three, explicitly adopts that version and saves version four.
   The existing restaurant journey also verifies filtered browsing/details and
   named deletion with linked-review impact text.

Database/API contracts separately exercise dependency failure before a write,
a uniqueness failure after catalog/retrieval mutation, linked-review deletion,
authorization/CSRF and confirmation/version checks. Five cancellation cases
cancel an actual asyncio task during preparation or after SQL mutation but
before commit. Full row snapshots include provenance, timestamps, vector values,
media and cleanup jobs; cancellation must propagate, preserve those rows and
allow a subsequent write. These are application-task cancellation contracts.
The admin interface offers preview discard and delete cancellation; it does
not offer an in-flight write Stop control or promise that disconnecting after
a commit undoes the write. Recommendation Stop/disconnect has separate evidence.

The sanitized report records source/script identities, versions, executed
database-contract counts, individual browser outcomes and isolation/cleanup.
Require `passed: true`, zero skipped/failed database contracts, all four browser
cases passing, and successful cleanup before accepting the task. On failure,
private redacted diagnostics remain at `.local-tmp/p11-admin-failure.log`;
the report omits exception messages, credentials, cookies and local media paths.
The verifier removes its container/anonymous database volume and private work
directory on completion. Ignored Playwright failure artifacts may remain in
`frontend/test-results/` and contain only synthetic fixture activity.

This verifies administrator behavior with a small isolated catalog and controlled
extraction. Full-corpus setup and paid provider/six-agent evidence remain the
separate P11-01–04 records. Portfolio screenshots, course grading requirements,
complete-release approval, source/entity-review and publication/history blockers
remain separate. See the [recorded evidence](../evaluation/phase11/README.md).
