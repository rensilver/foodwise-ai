# Clean-checkout local setup (P11-01)

Run from a fresh checkout of `foodwise-ai` on Linux x86_64. This sequence
builds the current application, restores the separately held recipe archive,
downloads pinned CPU models, initializes a new database and starts Compose.
[Rehearsal evidence](../evaluation/phase11/README.md) records the tested revision,
versions, recovery inputs and results. Public hosting remains deferred.

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
  compose run --rm --no-deps --workdir /setup \
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

Fresh full-corpus setup should report 329 entities (210 restaurants, 109 recipes,
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
Migration/idempotency/restart acceptance, backup/restore, paid live
recommendations and administrator demonstrations remain P11-02 through P11-05.
Delete volumes only for an explicitly disposable rehearsal project after its
results have been recorded; preserve the developer's real stack and settings.
