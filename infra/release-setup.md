# Clean-checkout local setup (P11-01)

Run from a fresh checkout of `foodwise-ai` on Linux x86_64. This sequence
builds the current application, restores the separately held recipe archive,
downloads pinned CPU models, initializes a new database and starts Compose.
[Rehearsal evidence](../evaluation/phase11/README.md) records the tested revision,
versions, recovery inputs and results. Public hosting remains deferred.
For post-setup diagnostics, provider/dependency failures and measured limits,
use the [local operation and troubleshooting guide](local-operations.md).

## Checkout and pinned tools

Clone the repository into a new directory and enter its root. Do not copy an
existing `.env`, `.venv`, `node_modules`, database volume or generated indexes.
Use Python 3.12.14, uv 0.12.5, Node 24.19.0 and pnpm 12.8.1, as pinned in
[the developer workflow](development.md#locked-setup). Docker Engine and Compose
are required; Compose must support `!override` when isolating rehearsal ports
(the recorded run uses Compose 5.5.1). Keep sufficient disk and RAM for builds
and the separate CPU indexing processes; startup measurements alone do not
establish recommendation capacity.

From the root, install the locked host tools used for provisioning:

```bash
mkdir -p .local-tmp/scratch .local-tmp/uv-cache
export TMPDIR="$PWD/.local-tmp/scratch"
export UV_CACHE_DIR="$PWD/.local-tmp/uv-cache"
export NEXT_TELEMETRY_DISABLED=1
cd backend
uv python install 3.12.14
uv sync --locked
uv pip check
cd ../frontend
pnpm install --frozen-lockfile
cd ..
```

Container builds independently install production dependencies from the same
lockfiles, with digest-pinned Python/Node/uv base images. Host development
dependencies are not copied into images.

## Fresh local credentials

```bash
test -e .env || cp .env.example .env
chmod 600 .env
```

Edit that private file. Supply a fresh, owner-issued OpenAI API key with access
to the configured text and vision models (both default to `gpt-4o-mini`), a
Tavily key for live trends, two independently generated URL-safe database
passwords, and a new Argon2id administrator password hash. Generate database
passwords with `openssl rand -hex 32` for each field. To generate the hash
without putting the administrator password in command history, from `backend/`:

```bash
uv run --locked python -c 'from getpass import getpass; from argon2 import PasswordHasher; print(PasswordHasher(memory_cost=65536, time_cost=3, parallelism=1).hash(getpass("New local administrator password: ")))'
```

Store the hash as a single-quoted `ADMIN_PASSWORD_HASH` value so dollar signs
stay literal. Keep `LANGFUSE_ENABLED=false` and
`LANGFUSE_CONVERSATION_EXPORT_VERIFIED=false` for this rehearsal; optional
Cloud operations are P11-11/12. Keep secrets out of frontend environments,
shared command logs and Git. Changing dotenv passwords does not rotate an
existing database; this sequence initializes a new volume.

OpenAI/Tavily account issuance and rotation require the owner's account access.
Syntax validation and startup make no paid inference/search calls. Separately
opt-in [capability probes](../backend/README.md#phase-7-six-agent-workflow) and
live demonstration evidence do not become verified merely because Compose is
healthy. Blank Tavily permits startup but cannot satisfy live-trend release gates.

## Models and media recovery

In the root `.env`, set `MINILM_ROOT` and `CLIP_ROOT` to absolute paths beneath
this checkout's `.local-tmp/`. Use these same values in the provisioning shell:

```bash
export MINILM_ROOT="$PWD/.local-tmp/minilm"
export CLIP_ROOT="$PWD/.local-tmp/clip"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
cd backend
make provision-minilm
make provision-clip
cd ..
```

These commands download public Hugging Face weights into initially empty
directories. MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
produces 384-dimensional vectors; CLIP revision
`3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` produces 512-dimensional vectors.
Their manifests record SHA-256 file hashes, checked when encoders load. CI's
random models do not replace these pretrained bundles. Compose mounts the
bundles read-only and never downloads them at startup.

Restore the owner-held, recovered `synthetic-recipe-images.zip` to
`data/synthetic-recipe-images.zip`; use the nonempty recovered archive, not the
original zero-byte artifact. It remains Git-ignored. The importer validates
CRC, safe paths, expansion limits, decoding and the exact `recipe{id}.png`
associations for all 109 recipes. Do not substitute the placeholder image or
copy an existing generated media directory. The six JSON/text seed artifacts
and reviewed mapping/addition/correction ledgers are already committed.

Review imagery can be downloaded afresh using `--download-review-images` below,
only from approved course hosts. For offline recovery, restore the nine bounded
image download-cache files to the report's sibling `downloads/` directory,
using the existing import manifest to retain URL/hash associations. Missing
images and the 16 existing same-name/location review pairs must stay visible
in the import report. Course PDFs/notebooks require separate restoration for
course/source auditing; they are not runtime retrieval inputs.

## Build, initialize and start Compose

Use a new checkout's default project only when no existing `foodwise-ai` stack
or named volumes need preservation. Define `compose` in the current shell:

```bash
compose() { docker compose "$@"; }
```

For an isolated rehearsal, instead save this override as
`.local-tmp/rehearsal.yaml`. It keeps database/MCP private, assigns unused
localhost ports, and separates images and volumes from the normal project:

```yaml
services:
  backend:
    image: ${COMPOSE_PROJECT_NAME}-backend:rehearsal
    mem_limit: 2304m
    memswap_limit: 2304m
    ports: !override ["127.0.0.1::8000"]
  mcp:
    image: ${COMPOSE_PROJECT_NAME}-backend:rehearsal
    mem_limit: 1536m
    memswap_limit: 1536m
  frontend:
    image: ${COMPOSE_PROJECT_NAME}-frontend:rehearsal
    ports: !override ["127.0.0.1::3000"]
```

```bash
export COMPOSE_PROJECT_NAME="foodwise-setup-$(date +%s)"
compose() {
  docker compose --env-file .env --project-name "$COMPOSE_PROJECT_NAME" \
    -f compose.yaml -f compose.low-memory.yaml \
    -f .local-tmp/rehearsal.yaml "$@"
}
```

Keep the same function/files/project on every command. These memory ceilings
bound the rehearsal, including one-off CLIP indexing, but do not predict peaks
or establish full recommendation capacity.

Build services sequentially. The optional low-memory override limits the
frontend build heap and the serving containers; its 512 MiB MCP ceiling has
not been validated for resident CLIP inference. The rehearsal uses an override
with more MCP memory; avoid treating the old scaffold limits as full-runtime
limits. The commands below use the base configuration.

```bash
compose config --quiet
compose build backend
compose build frontend
compose up -d db --wait --wait-timeout 180
```

Initialize through one-off backend containers on the private Compose network.
The production image intentionally omits migrations/scripts and seed data;
mount only the required checkout directories read-only. The root dotenv file
is never mounted. `setup` below is a shell function, used from the root in the
same shell where model paths were exported. It inherits the backend's internal
database URL and writable named media volume. Reports and download caches go
to a private `.setup/` directory in that volume, outside generated media keys.

```bash
setup() {
  compose run --rm --no-deps -T --workdir /setup \
    --volume "$PWD/backend:/setup:ro" \
    --volume "$PWD/data:/seed:ro" \
    --volume "$PWD/evaluation:/evidence:ro" \
    --volume "$CLIP_ROOT:/var/lib/foodwise/models/clip:ro" \
    --env CLIP_ROOT=/var/lib/foodwise/models/clip \
    --env OMP_NUM_THREADS=1 --env MKL_NUM_THREADS=1 \
    --env OPENBLAS_NUM_THREADS=1 --env TOKENIZERS_PARALLELISM=false \
    backend "$@"
}
setup alembic upgrade head
setup python scripts/setup_checkpoints.py
setup python -m food_recommender.cli.ingestion import \
  --data-root /seed \
  --mapping /evidence/phase0/restaurant_reconciliation.json \
  --accepted /evidence/phase3/accepted_restaurant_additions.json \
  --corrections /evidence/phase3/restaurant_corrections.json \
  --recipe-zip /seed/synthetic-recipe-images.zip \
  --report /var/lib/foodwise/media/.setup/manifest.json \
  --download-review-images
setup python -m food_recommender.cli.text \
  --model-root /var/lib/foodwise/models/minilm index
setup python -m food_recommender.cli.image \
  --clip-root /var/lib/foodwise/models/clip index
compose up -d --no-build --wait --wait-timeout 180
compose ps
SETUP_BACKEND_ADDRESS="$(compose port backend 8000)"
SETUP_FRONTEND_ADDRESS="$(compose port frontend 3000)"
curl --fail "http://$SETUP_BACKEND_ADDRESS/api/v1/health/ready"
curl --fail "http://$SETUP_FRONTEND_ADDRESS/health/live"
curl --fail "http://$SETUP_FRONTEND_ADDRESS/api/v1/recipes?limit=1"
```

The address probes work for both the default ports and the isolated override's
dynamically assigned localhost ports.

Fresh full-corpus setup should report 329 seed records (210 restaurants, 109 recipes,
ten reviews), zero rejected items, 770 text vectors and 118 image vectors when
all nine review images are available. Inspect the import's unresolved report;
16 entity-review pairs are expected and are not silently merged. Readiness
requires migrations, library checkpoint tables, media access, a compatible
MiniLM bundle and reachable MCP; it does not certify provider access, populated
indexes or live trends. Index summaries and catalog/proxy probes provide the
separate setup evidence. Retrying an interrupted setup uses the existing
ingestion/index checkpoints; never remove owner volumes to recover from an error.

Open the frontend address printed by `compose port frontend 3000` to browse the
synthetic catalog (normally `http://127.0.0.1:3000`). Logs use redacted
application fields. Stop this stack with `docker compose down`, which preserves
data. Use `compose down` when the helper selects an isolated project.
Migration/idempotency/restart acceptance is documented below. Paired backups
and fresh-volume restore are covered by the [P11-03 recovery guide](backup-restore.md).
For paid live recommendations and isolated administrator demonstrations, use
the [P11-04 live guide](live-demo.md) and [P11-05 admin guide](admin-demo.md).
Delete volumes only for an explicitly disposable rehearsal project after its
results have been recorded; preserve the developer's real stack and settings.

## Migration, ingestion and restart verification (P11-02)

After the locked host installation and model/media recovery above, run this
from the repository root. `--review-cache` selects the nine original review
download files named by URL hash (`*.bin`), as produced in the import report's
sibling `downloads/` directory. The verifier copies those inputs into its new
media volume, then validates/decodes them through the normal importer. It uses
the recovered ZIP at `data/synthetic-recipe-images.zip` and refuses incomplete
imports. Choose your recovered cache directory explicitly.

If the initialized stack above still exists, recover its nine cached originals
with the same `compose` helper before running the verifier:

```bash
mkdir -p .local-tmp/ingestion
compose cp backend:/var/lib/foodwise/media/.setup/downloads .local-tmp/ingestion/downloads
```

Then run:

```bash
backend/.venv/bin/python infra/verify_persistence.py \
  --minilm-root "$MINILM_ROOT" \
  --clip-root "$CLIP_ROOT" \
  --review-cache .local-tmp/ingestion/downloads \
  --output .local-tmp/p11-02-report.json
```

The [verifier](verify_persistence.py) builds the current backend/frontend in a
new randomly named Compose project, with independent credentials, images,
volumes and localhost ports. It does not read the root `.env`. Provider settings
are synthetic, Tavily is absent and Langfuse is disabled. It makes no paid
provider calls or model/media downloads. Private redacted command logs live in
the ignored `.local-tmp/p11-02-*/` directory.

It upgrades all Alembic revisions on an empty database, downgrades that empty
database to base, upgrades again, checks model/migration parity and initializes
the supported LangGraph schema. It checks HTTP readiness/liveness before
initialization, after initialization, during database/MCP outages and after
recovery. Separate adapter probes check missing media and encoder paths.
Readiness can pass for an empty catalog: it checks dependencies, not catalog
population or provider access.

Import/index acceptance requires 329 first imports, 329 unchanged repeat imports,
zero rejects, the 16 existing entity-review issues, 770 MiniLM vectors and 118
CLIP vectors. Repeated indexing must embed nothing. Complete row hashes include
IDs, content, provenance, timestamps, versions, vector values and checkpoints;
media checks include file hashes, sizes and decoding. Repeated migrations and
checkpoint setup must preserve those snapshots too.

The restart probes create an owned conversation/upload over HTTP, store a
synthetic message and hard preference through the application repository, and
save a synthetic control graph through the real PostgreSQL saver. They compare
all rows and media after `compose restart` and after `compose down`/`up` without
removing volumes. History, preferences, image bytes, ownership denial and the
frontend catalog proxy must survive. A new probe process advances the retained
checkpoint while preserving its restriction; this is a persistence check, not
the live six-agent demonstration in P11-04.

The verifier removes only its own containers/network/volumes/image tags and
temporary credentials, then checks existing containers' identities, start times
and restart counts. A failure exits nonzero and writes a sanitized report;
inspect its private logs before retrying. Do not substitute an owner's project
or delete existing volumes. The committed [P11-02 evidence](../evaluation/phase11/README.md#p11-02--migrations-idempotency-readiness-and-restarts)
records the actual tested result; see the [P11-03 recovery guide](backup-restore.md)
for the separate backup/restore rehearsal.
