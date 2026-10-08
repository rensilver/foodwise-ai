# Release module and CLI rehearsal (P11-10)

The 2026-10-08 rehearsal checks the release package from an archived checkout,
with a fresh virtual environment and a non-editable wheel installation. Its
[recorded evidence](../evaluation/phase11/README.md#p11-10--clean-checkout-paths-and-model-registration)
and [machine-readable report](../evaluation/phase11/package_paths_report.json)
identify the exact source revision, versions and results. This is a package and
migration check; full application setup and live acceptance have their separate
[release setup](release-setup.md) and [capability gate](../evaluation/phase11/release-gate.md).

## Current entrypoints and working directories

Run Python commands through `uv run --locked` from `backend/` on the host.
The production image already has the installed interpreter on `PATH`.

| Capability | Current entrypoint | Invocation |
| --- | --- | --- |
| HTTP recommendations/catalog/admin | [api/main.py](../backend/src/food_recommender/api/main.py) | `uvicorn food_recommender.api.main:create_app --factory` |
| HTTP MCP | [mcp/server.py](../backend/src/food_recommender/mcp/server.py) | `uvicorn food_recommender.mcp.server:create_app --factory` |
| stdio MCP | Same server module | `python -m food_recommender.mcp.server --transport stdio --env-file ../.env` |
| Configuration diagnostics | [infrastructure/config.py](../backend/src/food_recommender/infrastructure/config.py) | `python -m food_recommender.infrastructure.config --env-file ../.env` |
| Seed import/extraction preview | [cli/ingestion.py](../backend/src/food_recommender/cli/ingestion.py) | `python -m food_recommender.cli.ingestion import` or `preview`, with explicit input/output flags |
| MiniLM index/search | [cli/text.py](../backend/src/food_recommender/cli/text.py) | `python -m food_recommender.cli.text --model-root "$MINILM_ROOT" index` or `search` |
| CLIP index/search | [cli/image.py](../backend/src/food_recommender/cli/image.py) | `python -m food_recommender.cli.image --clip-root "$CLIP_ROOT" index` or `search` |
| Combined text/image search | [cli/multimodal.py](../backend/src/food_recommender/cli/multimodal.py) | `python -m food_recommender.cli.multimodal`, with model/query/media flags |
| Application migrations | [alembic.ini](../backend/alembic.ini), [migrations/env.py](../backend/migrations/env.py) | `alembic upgrade head`, then `alembic check` |
| LangGraph checkpoint setup | [scripts/setup_checkpoints.py](../backend/scripts/setup_checkpoints.py) | `python scripts/setup_checkpoints.py` after migrations |
| Public model provisioning | [scripts/provision_minilm.py](../backend/scripts/provision_minilm.py), [scripts/provision_clip.py](../backend/scripts/provision_clip.py) | `make provision-minilm`, `make provision-clip` with their model-root environment variables |
| Committed media cleanup | [scripts/cleanup_media.py](../backend/scripts/cleanup_media.py) | `python scripts/cleanup_media.py` with database/media configuration |
| OpenAPI export/drift | [scripts/export_openapi.py](../backend/scripts/export_openapi.py) | `make api-schema`, `make api-schema-check` |

The [package guide](../backend/PACKAGES.md#cli-path-changes) maps former CLI
locations to the current modules. There are no compatibility modules at those
former paths. Imports alone do not construct services or run commands.

Developer scripts are outside the wheel. Most run as files from `backend/`;
file execution puts `backend/scripts` on Python's search path for sibling
helpers. The optional telemetry commands use `python -m scripts.audit_langfuse_cloud`,
`scripts.measure_telemetry_overhead`, `scripts.export_phase10_scores` and
`scripts.purge_langfuse_traces`, matching the [Makefile](../backend/Makefile).
Use each documented invocation rather than converting all scripts to one style.
Import/help verification does not authorize or execute live provider/Cloud calls.

The container runtime contains the installed `food_recommender` package, with
no checkout scripts, Alembic configuration, seeds or evaluation ledgers. The
[read-only setup mounts](release-setup.md#build-initialize-and-start-compose) supply those
files under `/setup`, `/seed` and `/evidence`; setup runs from `/setup`. Keep
ingestion provenance and media arguments explicit there, since host source-tree
defaults do not locate mounted data from inside an installed wheel.

## Reproduce package checks

Use the pinned tools and a shell without backend credentials. From the root:

```bash
mkdir -p .local-tmp/scratch .local-tmp/uv-cache
export TMPDIR="$PWD/.local-tmp/scratch"
export UV_CACHE_DIR="$PWD/.local-tmp/uv-cache"
release_checkout=$(mktemp -d "$PWD/.local-tmp/release-paths.XXXXXX")
git archive HEAD | tar -x -C "$release_checkout"
cd "$release_checkout/backend"
uv sync --locked --no-editable
uv pip check
uv lock --check --offline
uv run --locked --no-editable python -c 'from pathlib import Path; import food_recommender; assert "site-packages" in Path(food_recommender.__file__).parts'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked --no-editable pytest \
  -p pytest_asyncio.plugin tests/contract/test_package_boundaries.py -q
uv run --locked --no-editable python scripts/export_openapi.py --check
uv run --locked --no-editable alembic heads
uv run --locked --no-editable alembic upgrade head --sql
```

The recorded installation also used `--offline`, with a populated shared uv
cache. The checkout received no existing `.env`, `.venv`, `node_modules`, model
bundles or media. All runtime imports resolved from its installed wheel.
Alembic intentionally uses the checkout's `src` through `prepend_sys_path`;
the separate cold-process probe checks installed-wheel ORM registration.

From that checkout's `backend/`, parser checks need no database, media or models:

```bash
uv run --locked --no-editable python -m food_recommender.cli.ingestion --help
uv run --locked --no-editable python -m food_recommender.cli.ingestion import --help
uv run --locked --no-editable python -m food_recommender.cli.ingestion preview --help
uv run --locked --no-editable python -m food_recommender.cli.text --help
uv run --locked --no-editable python -m food_recommender.cli.text --model-root /unavailable index --help
uv run --locked --no-editable python -m food_recommender.cli.text --model-root /unavailable search --help
uv run --locked --no-editable python -m food_recommender.cli.image --help
uv run --locked --no-editable python -m food_recommender.cli.image --clip-root /unavailable index --help
uv run --locked --no-editable python -m food_recommender.cli.image --clip-root /unavailable search --help
uv run --locked --no-editable python -m food_recommender.cli.multimodal --help
uv run --locked --no-editable python -m food_recommender.mcp.server --help
uv run --locked --no-editable python -m food_recommender.infrastructure.config --help
```

The additional recorded cold-process probes import all runtime modules in both
orders with DNS/socket, SQLAlchemy engine and HTTP client construction blocked,
and reject imports of Torch, Transformers, Sentence Transformers and Langfuse.
The locked LangChain/LangSmith dependency imports OpenTelemetry SDK definitions
transitively; this is permitted while network/client construction stays blocked.
All developer scripts import under network/engine/client guards, without running
their `__main__` blocks. The tiny fixture provisioner imports model SDK
definitions; it does not build models in that probe.

## Metadata registration and real database checks

[models/__init__.py](../backend/src/food_recommender/infrastructure/persistence/models/__init__.py)
is the complete registry. It imports eight mapping modules (`admin`, `catalog`,
`cleanup`, `context`, `embeddings`, `ingestion`, `provenance`, `trends`) and exports
`Base`. [Alembic](../backend/migrations/env.py) imports that registry; individual
mappings import [models/base.py](../backend/src/food_recommender/infrastructure/persistence/models/base.py).
Importing the registry in a fresh process registers 20 application tables and
resolves all 21 foreign keys without importing repositories, engines, encoders,
providers, composition or LangGraph. The supported checkpoint schema is separate
from application ORM metadata. The optional SQLite telemetry journal is also
outside the ORM registry.

Initialize an isolated `foodwise_test` database and limited application role using
the [CI database instructions](ci.md#reproduce-the-database-and-model-checks-locally).
Then run from the archived checkout's `backend/` with `TEST_DATABASE_URL` set:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked --no-editable pytest \
  -p pytest_asyncio.plugin \
  tests/integration/test_catalog_models.py \
  tests/integration/test_embedding_models.py \
  tests/integration/test_context_models.py \
  tests/integration/test_provenance_models.py \
  tests/integration/test_search_schema.py -q
export DATABASE_URL="$TEST_DATABASE_URL"
uv run --locked --no-editable alembic upgrade head
uv run --locked --no-editable alembic check
uv run --locked --no-editable alembic current
uv run --locked --no-editable python scripts/setup_checkpoints.py
uv run --locked --no-editable python scripts/setup_checkpoints.py
uv run --locked --no-editable alembic downgrade base
uv run --locked --no-editable alembic upgrade head
uv run --locked --no-editable alembic check
```

The downgrade/re-upgrade rehearsal uses only the disposable database. Remove
that test container afterward using the CI cleanup command. Ordinary migration
execution reads the explicitly exported database URL, requires no provider keys
and does not load dotenv files. Both checkpoint calls are idempotent; the
checkpoint library owns its four tables independently of the nine Alembic
revisions ending at `0009_admin`.

Frontend behavior and full live inference are unchanged by this documentation
alignment; their recorded acceptance is linked from the local capability gate.
P11-09 final review, P11-11/12 optional Cloud operations, entity review and
original-history/publication work remain open.
