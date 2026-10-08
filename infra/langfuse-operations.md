# Optional Langfuse Cloud operations (P11-11/12)

FoodWiseAI operates locally with tracing disabled. The current configuration is
`LANGFUSE_ENABLED=false` and `LANGFUSE_CONVERSATION_EXPORT_VERIFIED=false`.
The dedicated US Cloud project and project-scoped keys are usable; the owner
confirmed the basic Hobby plan on 2026-10-08. Keep both flags off for ordinary
conversations while the operational gates below remain open. The
[Phase 11 receipts](../evaluation/phase11/README.md#p11-1112--optional-cloud-operations-and-demonstration)
separate application acceptance, the synthetic Cloud demonstration and unresolved
account/retention controls. Earlier [Phase 10 reports](../evaluation/phase10/README.md)
remain unchanged.

## Project, region and quota

Use the existing dedicated project in `https://us.cloud.langfuse.com`; EU and JP
have separate approved endpoints. The adapter requires an explicit region and
never substitutes a default. Keep project public/secret keys in ignored
server-side configuration. Neither frontend nor MCP needs Langfuse credentials.
No new account, subscription, organization key or local Langfuse stack is required.

Hobby currently includes 50,000 monthly units, a 30-day data-access window and
30 general/Observations-v2 read requests per minute. A unit is a trace,
observation or score; the pilot's serialized bytes are not billing units.
[Pricing](https://langfuse.com/pricing),
[unit definition](https://langfuse.com/docs/administration/billable-units).
The project's current monthly consumption/remaining organization allowance has
not been independently confirmed. Check the account's usage report before
enabling export, and record the billing period and counts without account IDs.
The project API's successful authentication is not a quota check.

The predeclared forecast budget is 80% of the Hobby allowance. For 100 turns/day,
the earlier 14-observation pilot plus one trace and three applicable scores
forecasts 54,000 units/month, or 27,000 at whole-trace sampling of 0.5. This is a
forecast; local evaluations always include all fixtures and are independent of
sampling. The synthetic audit is fully sampled and paces reads at least 2.2
seconds apart. Quota/401/429/timeout behavior is tested with fake boundaries,
without deliberately exhausting the owner's Cloud allowance.

## Synthetic demonstration and private references

From `backend/`, with the locked environment installed:

```bash
uv run --locked python -m scripts.phase11_langfuse_demo \
  --enable-cloud \
  --env-file ../.env \
  --private-dir ../.local-tmp/langfuse-release-demo-01 \
  --output ../evaluation/phase11/langfuse_demo_report.json
```

Use a new private directory for each run. This explicit opt-in performs the
real graph and OpenAI HTTP adapter against controlled inference/tool fixtures,
then sends sanitized observations and locally calculated scores to Cloud.
It does not call OpenAI/Tavily, upload hosted datasets or use Experiment helpers,
prompts, images, comments, reasoning or hosted judges. The program temporarily
enables only its synthetic lifecycle; it does not edit `.env` or enable normal
application export.

Twelve labeled fixture turns plus eight scenario turns produce 20 demonstration
traces. Scores are deliberately submitted twice with identical IDs to verify
upsert deduplication. The audit checks current Observations v2/Scores v3,
execution counts, types, parentage, durations, revisions, opaque sessions,
empty content fields, model/usage values and score associations. Failed/cancelled
provider attempts retain unknown usage. Current API filters include trace IDs
and fixed time bounds; pagination has a hard page limit and rejects repeated
cursors and out-of-scope rows.

The pilot buffers at most 2,048 sanitized observations and sends batches of 32
after generating the fixtures. This avoids the application's journal writer
lock competing with network delivery during new synthetic trace registrations.
Live journal lock contention can drop tracing while culinary execution
continues; this distinction is an operational limitation, not a claim of
complete ordinary-conversation delivery. The measured application SDK overhead
uses its usual fake-exporter path, separately from this pilot-only buffering.

Private `trace-links.json`, read-back data and the opaque SQLite journal stay
under ignored `.local-tmp`, with directory mode `0700` and file mode `0600`.
Open the links while signed into the owner's project. They remain private;
public sharing is not enabled. Committed reports contain counts, names,
violations and versions, without project/trace/score IDs or credentials.
Twenty demonstration traces remain for inspection and require manual cleanup.

Pinned CLI discovery and read-back use `langfuse-cli@1.2.4` with Node 24.19.0:

```bash
npx --yes langfuse-cli@1.2.4 api __schema --json
npx --yes langfuse-cli@1.2.4 api observations list --help
npx --yes langfuse-cli@1.2.4 api scores list --help
npx --yes langfuse-cli@1.2.4 api projects list-api-keys --help
```

For authenticated CLI reads, load only `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY` and the explicit regional host into the subprocess
environment from the ignored configuration; set `LANGFUSE_HOST` to that host.
Keep output private. The tested `--json` envelope is `status/headers/body`;
observation rows are `body.data`. Scope reads to a known new trace and a fixed
time range, selecting the required field groups. Do not use `--curl` with real
credentials: it renders an authenticated request. The CLI remains developer
tooling outside the application dependency manifests.

## Disable, outages and credential rotation

For disable or emergency rollback, keep both tracing flags false and recreate
the backend using the installation's existing Compose files/project. A simple
container restart does not replace its environment. Existing database/media
volumes and local reports remain in place. Readiness does not depend on Cloud,
and interrupted message POSTs are recovered from history without automatic replay.

The offline credential-rotation rehearsal proves a fresh tracing lifecycle
consumes replacement keys and settings redact them. Actual Cloud issuance and
revocation remain owner-console steps: project keys cannot administer project
keys through the organization-management API. Current CLI schema explicitly
requires an organization-scoped key for those operations; no organization key
was requested or added.

1. Disable export and stop/drain the existing tracing lifecycle. Preserve the
   private journal and correlation key so existing tombstones still match.
2. The owner creates a replacement project key pair in the same region/project,
   stores it in ignored server configuration, and recreates the backend.
3. Run the synthetic demonstration with a fresh private directory. Confirm
   authenticated project access and stored observations/scores with the new pair.
4. The owner revokes the old pair and verifies it fails authentication, then
   removes its local copies. Keep normal conversation export disabled until the
   account quota and retention/deletion gates are independently satisfied.

Possession of working `.env` keys does not prove their issue/rotation date.
Changing the correlation key is a separate migration: replacing it can prevent
old conversation tombstones from matching newly calculated HMAC references.

## Retention and deletion

Hobby has no automatic retention policy. Its access window does not delete data.
Trace deletion removes associated observations/scores asynchronously; the
provider documents usual completion within 15 minutes and requires read-back
rather than providing a completion notification.
[Retention](https://langfuse.com/docs/administration/data-retention),
[deletion semantics](https://langfuse.com/docs/administration/data-deletion).

The live rehearsal creates one additional synthetic trace, tombstones its
session locally, and deletes only that newly created trace. It verifies absent
observations and repeats the read after a 15-second quiet period. Reopening the
journal rejects late exports and new traces for that tombstoned session. This
bounded check does not verify inaccessible historical data, provider backups
or unlimited delayed ingestion. A corrupt-journal test preserves the damaged
file and disables export before SDK construction; silent reconstruction of
lost tombstones is not supported.

For later synthetic cleanup, use the retained private trace IDs to submit only
that demonstration's batch through the documented trace DELETE endpoint, and
read back Observations v2 and associated Scores v3 until both are absent.
Pause producers/tombstone their sessions before deleting. Keep fixed windows,
follow cursors and respect the read limit. The existing Phase 10 purge script
uses a two-hour recent window and is not proof of deletion for older demos;
do not use it to certify inaccessible history. Cloud session deletion similarly
requires careful collection of trace IDs before asynchronous mutation.
No project-wide delete or deletion of older owner's traces was performed.

Automatic purge scheduling, recovery of lost/corrupt journals, inaccessible old
history, actual key revocation and current remaining quota are still unverified.
The fresh SDK measurement also misses the existing latency limits: disabled/enabled
warm p95 is 25.56/42.01 ms, adding 16.45 ms (64.3%), above the 10 ms/25% budget.
Additional peak RSS is 26.02 MiB, within its 96 MiB bound. These are 100 warm
samples per mode in separate processes on one host, with uncontrolled page
cache/load and a fake exporter; they do not measure remote network latency.
Normal conversation export therefore remains off and P11-11 remains open.

## SDK upgrade and rollback

The application stays locked to Python SDK 4.16.0 and OpenTelemetry 1.45.0.
The latest stable SDK checked on 2026-10-08 is 4.17.0. The upgrade rehearsal
uses a disposable, non-editable installation, not the owner's environment.
Run from that separate checkout's `backend/`:

```bash
uv sync --locked --no-editable
uv pip install --python .venv/bin/python langfuse==4.17.0
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest \
  -p pytest_asyncio.plugin \
  tests/unit/test_phase10_tracing.py \
  tests/unit/test_phase10_tracing_isolation.py \
  tests/unit/test_phase10_trace_deletion.py \
  tests/unit/test_phase10_scores.py \
  tests/unit/test_phase11_langfuse_demo.py \
  tests/unit/test_phase11_langfuse_operations.py \
  tests/contract/test_package_boundaries.py -q
uv sync --locked --no-editable
```

Run the same contracts after lock restoration to verify rollback to 4.16.0.
The recorded installation/rollback also uses `--offline` with a populated uv
cache. Candidate live Cloud delivery is a separate check before adopting a new
application pin; this rehearsal does not modify `pyproject.toml` or `uv.lock`.
Review the [SDK upgrade path](https://langfuse.com/docs/observability/sdk/upgrade-path)
and [compatibility cutoff](https://langfuse.com/docs/compatibility) for each
upgrade. Current reads use Observations v2/Scores v3; the published legacy
Cloud cutoff remains November 16, 2026. Trace DELETE remains the supported
mutation even as older trace-read APIs are retired.

The reviewed upstream skill is pinned at
[`104acd9aa7b1f431066cd9fe4b0b431a0188e642`](https://github.com/langfuse/skills/blob/104acd9aa7b1f431066cd9fe4b0b431a0188e642/skills/langfuse/SKILL.md),
reviewed on 2026-10-08, with skill/reference hashes recorded in the demo receipt.
Its current API/CLI and send/read-back/audit guidance is applied. The repository's
metadata-only policy takes precedence over upstream suggestions to collect
content, reasoning, user IDs, media or hosted evaluation datasets.
