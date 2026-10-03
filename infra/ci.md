# Continuous integration (P01-07)

[The GitHub Actions workflow](../.github/workflows/ci.yml) runs on pushes,
pull requests and manual dispatches. Two Ubuntu 24.04 jobs use commit-pinned
actions, the existing locked runtimes/dependencies, read-only repository
permissions and bounded job times. Neither job needs repository secrets or a
root `.env`.

The backend job installs with `uv sync --locked`, initializes an isolated
PostgreSQL 16/pgvector 0.8.6 service, provisions local model fixtures, then runs
`make check` and the redacting source scan. The frontend job installs with
`pnpm install --frozen-lockfile`, runs `pnpm check`, installs the locked
Chromium revision and Linux libraries, then runs `pnpm test:e2e`. That browser
command also builds and starts the production standalone app.

The workflow follows the official
[GitHub PostgreSQL service-container guide](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)
and [uv Actions guide](https://docs.astral.sh/uv/guides/integration/github/).
The setup actions install dependencies from the network; tests use the local
services and fixtures below.

## External providers and models

[Test support](../backend/tests/conftest.py) provides canned Groq/Tavily
responses through `httpx.MockTransport`; [SDK contracts](../backend/tests/contract/test_offline_fixtures.py)
exercise both pinned clients with synthetic credentials. Fake endpoints reject
unexpected requests. An automatic fixture blocks external Python socket
connections and DNS resolution while allowing loopback integration services.
Existing service tests use injected/mocked readiness boundaries. Tests do not
load owner credentials or call paid providers.

[The provisioning script](../backend/scripts/provision_test_models.py) creates
small, seeded, randomly initialized BERT and CLIP models in an ignored
directory **before** test execution. BERT has 384-dimensional hidden states;
CLIP has 512-dimensional text/image projections. The contract loads saved
files with `local_files_only=True` and checks finite CPU outputs and dimensions.
CI also sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, following
[Transformers offline guidance](https://huggingface.co/docs/transformers/installation#offline-mode).
There are no pretrained downloads. These are interface fixtures; they do not
measure relevance or replace the planned MiniLM/CLIP retrieval models.

CI must supply `TEST_DATABASE_URL` and `TEST_MODEL_ROOT`; missing settings
fail tests rather than skip them. Ordinary local `make test` skips only the
database/model contracts when their settings are absent, with explicit reasons.
Configured but missing/broken services or model files always fail.

## Reproduce the database and model checks locally

Use the existing locked backend setup first. From the repository root, start a
fresh disposable database with the same image used by CI. The name below must
be unused. This container uses synthetic credentials, a random localhost port,
and no application database or persistent project volume:

```bash
docker run --detach --rm --name foodwise-ci-postgres \
  --memory 256m --memory-swap 256m \
  -e POSTGRES_DB=foodwise_test \
  -e POSTGRES_PASSWORD=synthetic-ci-database-password \
  -p 127.0.0.1::5432 \
  pgvector/pgvector:pg16@sha256:a36250871de0833b8757561c72f2477ef1ddd1101afa4e617fb552e0de514c6b \
  -c shared_buffers=64MB -c max_connections=20
docker exec foodwise-ci-postgres pg_isready -U postgres -d foodwise_test
```

Wait until the last command reports accepting connections, then run in the
same shell:

```bash
test_db_port=$(docker port foodwise-ci-postgres 5432 | sed 's/.*://')
export TEST_DATABASE_ADMIN_URL="postgresql://postgres:synthetic-ci-database-password@127.0.0.1:${test_db_port}/foodwise_test"
export TEST_DATABASE_URL="postgresql://foodwise_test_app:synthetic-ci-application-password@127.0.0.1:${test_db_port}/foodwise_test"
export TEST_MODEL_ROOT="$PWD/.local-tmp/test-models"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p .local-tmp/scratch
export TMPDIR="$PWD/.local-tmp/scratch"
cd backend
uv run --locked python scripts/bootstrap_test_database.py
make provision-test-models
make check
```

The bootstrap is for a fresh service and runs once. It requires a localhost
database named `foodwise_test`, creates the vector extension and a limited
application login, and removes public database/schema privileges. The test role
can connect and create ordinary tables but cannot administer PostgreSQL.
The [four database contracts](../backend/tests/integration/test_postgres.py)
check versions/privileges, 384/512-dimensional adapter roundtrips and cosine
ordering, rollback of a partially completed invalid vector write, and real
async database/media readiness. Table creation and data changes roll back after
each test. P02-02 adds
[catalog integration contracts](../backend/tests/integration/test_catalog_models.py)
for real Alembic migrations, schema/model parity, canonical/source identity,
review foreign keys and nullable metadata. Those tests apply migrations using
an injected SQLAlchemy connection and roll back their tables/data on completion.
The same CI database role runs both suites without additional privileges.
P02-03 adds [provenance contracts](../backend/tests/integration/test_provenance_models.py)
for source revisions, raw records, document/media associations, attribution,
hashes/dates, duplicate rejection and rollback. The shared fixture uses the same
limited role and transaction isolation; upgrade/downgrade checks preserve the
existing catalog. P02-04/P02-05 add separate vector tables, lexical fields and filter indexes.
P02-06 adds sessions/conversations/profiles/trend evidence and real LangGraph
checkpoint persistence tests. Bootstrap precreates the isolated checkpoint
schema for the limited role; tests use supported, idempotent saver setup.
P02-07/P02-08 add real async repository transactions, expected-version races,
rollback, cache and session-isolation acceptance. P02-09 adds supported checkpoint
erasure, shared-upload lifetimes, durable cleanup and filesystem boundary tests.
The committed race/deletion cases use unique fixture identities and clean them
afterward; ordinary contracts remain transaction-isolated. Retrieval and
agent execution remain later tasks.

For only the database suite, run `make test-integration` from `backend/` with
`TEST_DATABASE_URL` still set. This target fails immediately if the setting is
missing. Stop the disposable container afterward; `--rm` also removes its
anonymous storage:

```bash
docker stop foodwise-ci-postgres
unset TEST_DATABASE_ADMIN_URL TEST_DATABASE_URL TEST_MODEL_ROOT
```

Frontend reproduction uses the existing [quality/browser guide](../frontend/README.md#quality-scripts-p01-06):
run `pnpm check`, `pnpm test:e2e:install` and `pnpm test:e2e` from `frontend/`.
Reuse the same `PLAYWRIGHT_BROWSERS_PATH` for installation and testing.

## Verification limits

Local workflow commands and static workflow validation are recorded in
[CHECKLIST.md](../CHECKLIST.md). A hosted Actions run requires pushing the
workflow to GitHub; local verification does not establish a hosted green run.
Phase 2 persistence is verified. Full recommendation flows, pretrained retrieval
and browser acceptance journeys remain their later tasks.
