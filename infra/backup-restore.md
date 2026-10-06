# PostgreSQL and media recovery (P11-03)

Back up PostgreSQL and the complete media volume together during a local
maintenance window. Stop browser traffic, API/MCP/frontend processes and any
host ingestion/indexing/cleanup jobs first. PostgreSQL remains running for
`pg_dump`; no application writer may restart until both archives and their
checksums exist. This keeps database references and filesystem bytes aligned.

Use the pinned PostgreSQL 16/pgvector image and the same application revision
on recovery. The custom-format dump includes application schema/data, vector
values, constraints, provenance, browser sessions, profiles, messages and the
separate `foodwise_checkpoints` schema. It preserves object ownership and grants
for the `foodwise` role. `pg_dump` does not export role passwords; a fresh target
must bootstrap that same limited role with independently supplied credentials.
The media archive includes hidden files such as `.setup/` recovery manifests
and original downloads. Model bundles, provider/admin credentials, course
artifacts and the recovered recipe ZIP are separate recovery inputs.

The tested procedure is an offline, same-version recovery. Online filesystem
snapshots, WAL/PITR and cross-version migrations have not been verified. See
PostgreSQL's [pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html) and
[pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html) contracts.

## Back up a selected local installation

Use the `compose` and `setup` helpers from the
[setup guide](release-setup.md#build-initialize-and-start-compose), with the
correct project, dotenv and override files. Finish or cancel active runs before
stopping services. Keep checkpoints from interrupted/cancelled work as stored;
restoring data does not authorize automatically resuming a disconnected POST.
The `setup` helper must include `-T` to disable TTY allocation before transferring
binary archives over stdin/stdout, as the current setup guide does.

Run from the repository root, in the same shell:

```bash
set -euo pipefail
umask 077
BACKUP_ROOT="$PWD/.local-tmp/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_ROOT"
compose stop frontend backend mcp
setup python -m scripts.probe_phase11_persistence snapshot | cat > "$BACKUP_ROOT/baseline.json"
setup python scripts/backup_media.py snapshot | cat > "$BACKUP_ROOT/volume.json"
compose exec -T db pg_dump -U postgres -d foodwise --format=custom | cat > "$BACKUP_ROOT/database.dump"
setup python scripts/backup_media.py create | cat > "$BACKUP_ROOT/media.tar"
(
  cd "$BACKUP_ROOT"
  sha256sum database.dump media.tar baseline.json volume.json > SHA256SUMS
  sha256sum --check SHA256SUMS
)
compose up -d --no-build --wait --wait-timeout 180
```

Stop on failure and inspect local logs. Do not treat a partial dump/media pair
as recoverable. Choose a new backup directory for a retry. Store the original
checksums with the archives; do not regenerate them after a transfer error.
Retain the tested source Git revision, pinned image/model versions and private
browser cookies separately if continued access to existing conversations is
needed. Session token hashes are restored, but a new browser without its
original cookie correctly cannot read another session's history or uploads.
The `cat` pipes keep Docker's stdin/stdout attached to pipes; this is required
by the tested Snap Docker packaging. `pipefail` makes upstream errors fatal.

Archives contain private history and media. Keep permissions private and store
any retained copy in owner-controlled storage outside Git. `.local-tmp/` is
ignored scratch storage, not durable backup storage. The rehearsal below
deletes its raw archives after verification; it does not create a retained
backup of the owner's installation.

## Restore into a fresh isolated project

Select a **new project with fresh database and media volumes** using the setup
guide's isolation override and new database passwords. Preserve the source
installation. Point its `compose`/`setup` helpers to the new project. Build the
matching application revision and recover its pinned model bundles first.
Set `BACKUP_ROOT` to the existing complete backup directory. Only the target
database should be started; do not migrate, seed or index it before restore.

```bash
set -euo pipefail
(
  cd "$BACKUP_ROOT"
  sha256sum --check SHA256SUMS
)
compose up -d db --wait --wait-timeout 180
test "$(compose exec -T db psql -U postgres -d foodwise -tAc "SELECT count(*) FROM pg_tables WHERE schemaname IN ('public','foodwise_checkpoints')")" = "0"
cat "$BACKUP_ROOT/database.dump" | compose exec -T db pg_restore -U postgres -d foodwise \
  --clean --if-exists --single-transaction --exit-on-error
cat "$BACKUP_ROOT/media.tar" | setup python scripts/backup_media.py restore
setup python -m scripts.probe_phase11_persistence snapshot | cat > "$BACKUP_ROOT/restored.json"
setup python scripts/backup_media.py snapshot | cat > "$BACKUP_ROOT/restored-volume.json"
cmp "$BACKUP_ROOT/baseline.json" "$BACKUP_ROOT/restored.json"
cmp "$BACKUP_ROOT/volume.json" "$BACKUP_ROOT/restored-volume.json"
setup alembic check
compose up -d --no-build --wait --wait-timeout 180
RESTORED_BACKEND_ADDRESS="$(compose port backend 8000)"
RESTORED_FRONTEND_ADDRESS="$(compose port frontend 3000)"
curl --fail "http://$RESTORED_BACKEND_ADDRESS/api/v1/health/ready"
curl --fail "http://$RESTORED_FRONTEND_ADDRESS/api/v1/recipes?limit=1"
```

`pg_restore --clean` replaces archived objects in the selected target; the
commands are intended only for the fresh isolated project above. Bootstrap
creates pgvector and the limited role before the dump restores their schemas,
objects and grants. Restore is a single database transaction with errors fatal.
Media restore requires an empty volume; it validates every archive entry before
staging files and never follows links. Restored files belong to the backend's
UID 10001, with private file/directory modes, and MCP still mounts media read-only.

If recovery fails, keep source services and backups intact. Stop the target,
inspect the error, and retry in new disposable target volumes. Start serving
only after database and complete media snapshots match. Browse source-backed
details/images, check text/image retrieval, and read history using the retained
browser cookie. Submit a new explicit follow-up to advance saved context;
never automatically replay a disconnected message request.

This workflow uses tracing disabled. An enabled Langfuse installation's local
journal is included in the complete volume archive while writers are stopped,
but external Cloud retention, purge state and secret rotation require the
separate P11-11/12 procedure. This rehearsal does not verify Cloud recovery.

## Reproduce the isolated acceptance rehearsal

After restoring the recipe ZIP, pinned models and nine original review download
cache files as documented in [setup](release-setup.md), run:

```bash
backend/.venv/bin/python infra/verify_backup_restore.py \
  --minilm-root "$MINILM_ROOT" \
  --clip-root "$CLIP_ROOT" \
  --review-cache .local-tmp/ingestion/downloads \
  --output .local-tmp/p11-03-report.json
```

The [verifier](verify_backup_restore.py) builds current production images and
seeds/indexes a disposable source from the original datasets. It creates an
owned synthetic conversation/upload, saves a hard preference and a synthetic
control graph through the real PostgreSQL saver, then quiesces services and
backs up both stores. It verifies archive hashes and tests corruption rejection
before restoring. It removes source volumes before creating the separate target
with new credentials. Owner dotenv/provider keys are never read, all provider
settings are synthetic, Tavily is absent and Langfuse is disabled.

Acceptance compares all table rows, vectors/checkpoints, constraints, ownership,
registered media hashes/decoding and the complete volume, including hidden
recovery files. Real search adapters repeat lexical and stored-vector queries
for restaurants/recipes and CLIP self-retrieval with the correct image/entity
identity. All 109 recipe image routes and citations must survive; nine review
images retain their linked restaurants and scoped retrieval access. An existing
session reads the same conversation/upload; strangers receive 404. A new probe
process advances the restored checkpoint from turn one to turn two while
retaining its hard preference. Conversation deletion must remove history,
profile, upload and checkpoint rows without changing catalog retrieval.
Next.js catalog proxy and readiness must pass after recovery.

The verifier exits nonzero on any failure, records a sanitized report, and
removes only its own containers/networks/volumes/image tags, temporary
credentials and raw backups. Private redacted logs remain in ignored
`.local-tmp/p11-03-*/` directories. Existing container identities, start times
and restart counts must remain unchanged. The
[committed evidence](../evaluation/phase11/README.md#p11-03--postgresql-and-media-backuprestore)
records the actual outcome; live six-agent demonstration remains P11-04.
