# Backend scaffold

The application package is `src/food_recommender`. P01-03 adds validated
configuration in the infrastructure package. P01-05 adds FastAPI and FastMCP
startup factories and local health probes. P01-08 adds composition roots,
application readiness dependencies, typed failures and structured logging.
P02-01 adds shared domain contracts and boundary validation. P02-02 adds catalog
persistence models and the initial migration. P02-03 adds source, document and
media provenance; agent execution, retrieval and
repository adapters remain planned. P01-02 pins Python 3.12.14 in
[.python-version](.python-version), uv 0.12.5 in
[pyproject.toml](pyproject.toml), and framework/provider dependencies in
[uv.lock](uv.lock). Hatchling packages `src/food_recommender` for editable
installation and wheel builds.

With uv 0.12.5 installed, run from `backend/`:

```bash
uv python install 3.12.14
uv sync --locked
uv pip check
uv run --locked python -c "import food_recommender; import fastapi; import fastmcp"
```

`uv sync --locked` installs the resolved dependency graph and fails if the
manifest and lock disagree. The environment is created in the ignored `.venv/`.
Dependencies cover FastAPI/Pydantic, SQLAlchemy 2/Alembic/async psycopg/pgvector,
LangGraph/PostgreSQL checkpoints, Groq, FastMCP, Tavily, and local embeddings.
Linux and Windows use CPU-only PyTorch from an explicit index; macOS uses
PyPI CPU wheels, following the [uv PyTorch guide](https://docs.astral.sh/uv/guides/integration/pytorch/).
Embedding model weights are separate downloads scheduled for retrieval work;
installation does not call paid providers or download models. The verified
installation target is Linux x86_64; other platforms have not been tested.

Container startup is documented in the [Compose guide](../infra/README.md).
The [developer workflow](../infra/development.md) collects setup, host-run
development commands, checks and migration/ingestion availability.
Catalog migration commands and quality scripts are documented below.
Framework imports do not establish application readiness.

## Backend configuration

[Settings](src/food_recommender/infrastructure/config.py) uses the pinned
[Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
dependency. Configuration is loaded explicitly with `load_settings()`;
importing the module does not load credentials. Environment names are
case-sensitive. A dotenv file is read only when selected with
`load_settings(env_file=Path("/absolute/path/to/.env"))`. It may contain settings
for other services, which this model ignores. Process environment values take
precedence over that file. Direct `Settings(GROQ_MODEL="configured-model", ...)`
values take precedence over environment values for dependency injection and tests.

| Environment variable | Contract |
| --- | --- |
| `GROQ_API_KEY` | Required nonempty secret token, without whitespace/control characters. |
| `GROQ_MODEL` | Defaults to `qwen/qwen3.8-27b`; explicit blank/invalid identifiers fail validation. |
| `GROQ_VISION_MODEL` | Independently configurable; initially defaults to `qwen/qwen3.8-27b`, even if the text model is overridden. |
| `TAVILY_API_KEY` | Optional secret token. Missing or whitespace-only values become `None`, indicating unavailable live trends. |
| `DATABASE_URL` | Required PostgreSQL URL with a user, host, database and valid optional port. `postgresql://` is normalized to `postgresql+psycopg://`; other drivers are rejected. The complete URL is stored as a secret. |
| `MCP_SERVER_URL` | Required HTTP(S) endpoint; credentials, query strings, fragments and port zero are rejected. Internal Compose hostnames are accepted. |
| `MEDIA_ROOT` | Required absolute, non-root path without `..` or NUL bytes. Loading does not create or inspect the directory. |
| `ADMIN_PASSWORD_HASH` | Required Argon2id v19 PHC encoding; plaintext and other hash formats are rejected. |

The administrator hash policy accepts memory costs of 19,456–262,144 KiB,
2–10 iterations and 1–16 parallel lanes, with a 16–64 byte salt and a 32–64
byte digest in canonical unpadded base64. Its minimum costs follow the
[OWASP Argon2id guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#argon2id).
Validation checks encoding and bounded costs. Generate a unique password hash
locally with an Argon2id PHC-capable tool using those costs and keep the password
separate; password verification and administrator sessions are future
authentication work. This project does not ship a default administrator password.

Settings are immutable and loaded afresh on each call. Each process factory
loads them once and injects them into its readiness adapter through the
[composition roots](src/food_recommender/composition.py).
Provider keys, the database URL and administrator hash use `SecretStr`, which
masks their representations and JSON serialization. Adapters must explicitly
call `get_secret_value()` when supplying a credential to its dependency.
`load_settings()` raises `ConfigurationError` containing field names, error
types and field-specific corrective guidance without supplied values. If directly inspecting a Pydantic
`ValidationError`, use `errors(include_input=False, include_context=False)`;
Pydantic's hidden-input setting protects the textual error only. This is a
backend configuration model and must never be returned through an API.

Loading makes no provider calls, database/MCP connections, directory writes or
model downloads. It does not verify credential validity, model capabilities,
service readiness or media permissions. Capability checks remain explicitly
opt-in future work; providers/models are never switched automatically.

### Local setup and offline diagnostics

Use the root [.env.example](../.env.example) as the template for a root `.env`
only if you do not already have local configuration. Keep an existing `.env`
and add missing entries manually. Required credentials are deliberately blank:
supply a fresh `GROQ_API_KEY` and your own `ADMIN_PASSWORD_HASH`. Leave
`TAVILY_API_KEY` blank for unavailable live trends, or supply a fresh key.
The example's PostgreSQL and MCP endpoints describe separately provisioned
host-run services; they do not start them. Add URL-encoded database credentials
when required and select your absolute media directory. Compose injects its
internal URLs and mounted media root; its database/MCP ports are unpublished.
Add its two database passwords as described in the infrastructure guide.

Write PHC hashes as `ADMIN_PASSWORD_HASH='<your generated PHC hash>'` with
single quotes to preserve `$` characters. Do not source the example as a shell
script; use the explicit dotenv loader. Provider keys and hashes must never
appear in `NEXT_PUBLIC_*`, Next.js `env` configuration, API responses or logs.

From `backend/`, validate a selected local file without printing its values:

```bash
uv run --locked python -m food_recommender.infrastructure.config --env-file ../.env
```

To validate settings supplied entirely through the process environment, omit
`--env-file`. The command returns `0` for valid syntax and `2` for invalid or
missing configuration, prints corrective instructions without a traceback,
and reports unavailable trends when Tavily is unconfigured. It performs no
service calls, media writes or model downloads. A valid configuration does
not establish database/MCP readiness or provider/model access.

The offline configuration contracts use synthetic credentials and temporary
dotenv files. The pytest suite below collects both the existing unittest cases
and native async tests.

P01-05 adds `/api/v1/health/live` and `/api/v1/health/ready` to the FastAPI
factory, and `/health/live` and `/health/ready` to the separate HTTP FastMCP
factory. Readiness checks local PostgreSQL/pgvector, mounted media and (for
FastAPI) MCP availability with bounded calls; failures return names/statuses
without exception details. No provider calls or model downloads occur.
Run all current offline backend contracts with `make test` from `backend/`.

The scaffold factories are `food_recommender.api.main:create_app` and
`food_recommender.mcp.server:create_app`. Compose runs them with Uvicorn
`--factory` on ports 8000/8001. The API requires the validated backend settings;
MCP validates only `DATABASE_URL` and `MEDIA_ROOT` and receives no provider/admin
secrets. Tools/resources and recommendation endpoints remain later phases.

| Package | Responsibility |
| --- | --- |
| `domain` | Entities, value types, dietary rules, and recommendation invariants; independent of frameworks and SDKs. |
| `application` | Use cases, dependency ports, and transaction boundaries. |
| `agents` | Six agent roles, prompts, typed graph state, and orchestration. |
| `retrieval` | Source routing, query planning, fusion, and evidence validation. |
| `ingestion` | Source adapters, manifests, validated extraction, and import CLI. |
| `infrastructure` | Persistence, provider, embedding, search, and media adapters. |
| `api` | FastAPI routes, dependencies, HTTP schemas, and SSE. |
| `mcp` | FastMCP server, client adapter, tools, and resources. |

Domain rules stay in `domain`; application use cases depend on ports. Frameworks
and provider SDKs connect through adapters. FastAPI and FastMCP share application
and retrieval services. Course notebooks are reference material, outside this
runtime package.

## Composition, errors and logging (P01-08)

The [composition module](src/food_recommender/composition.py) builds immutable
[Services](src/food_recommender/application/services.py) around the implemented
`ReadinessProbe` port. Backend readiness owns the complete backend settings;
MCP readiness receives only its independent database/media settings and checks
media without writes. Construction performs no service connections or model
loading. There are no placeholder repository/inference ports: introduce those
when their application use cases exist.

Both factories accept `settings`, `services` and `runtime` explicitly. The API
also retains the original `probe` argument for existing callers. Routes obtain
services through [get_services](src/food_recommender/api/dependencies.py);
tests can set `app.dependency_overrides[get_services]` to a provider returning
replacement services, following [FastAPI dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/).
MCP custom HTTP health routes use the services injected into its factory.
`Runtime` accepts a logger, monotonic clock and UUID generator; supplying it
avoids changing process logging in an embedding application or test.

[ApplicationError and ErrorCode](src/food_recommender/application/errors.py)
have no framework/provider imports. Raise `ApplicationError(code)` at a use-case
boundary and preserve an adapter exception with `raise ... from error` when
needed. Never use provider text or profile content as a public message. The
shared [HTTP boundary](src/food_recommender/infrastructure/http.py) returns
`{"error":{"code":...,"message":...,"retryable":...},"request_id":...}` using
fixed messages and Pydantic schemas; the API exposes the unexpected readiness
error schema in OpenAPI. API validation and HTTP exceptions use the same
envelope without echoing inputs, exception details or stack traces.

| Application code | Default HTTP status | Retryable |
| --- | --- | --- |
| `invalid_request` | 422 | No |
| `not_found` | 404 | No |
| `conflict` | 409 | No |
| `dependency_unavailable` | 503 | Yes |
| `internal_error` | 500 | No |

Framework HTTP exceptions retain their HTTP status. Expected readiness failures
retain the existing health payload containing dependency names/statuses.
MCP protocol responses keep FastMCP's native JSON-RPC contract; this shared
envelope handles unexpected HTTP failures before response headers start.
Cancellation propagates, and failures after headers propagate instead of
attempting a second response. Future SSE and culinary MCP tools must implement
their own typed in-stream/tool error contracts when those features arrive.

[Structured logging](src/food_recommender/infrastructure/observability.py)
uses JSON lines on stderr. Default factory startup replaces existing root and
registered SDK/Uvicorn handlers with the safe formatter; repeated configuration
does not duplicate records. Imports do not configure logging. Keep future
handlers behind this formatter and do not print request/provider payloads.
Logs contain timestamp, level, allowlisted event names, UUID request/run IDs,
error codes and finite nonnegative numeric metrics. Free-form messages,
tracebacks, logger names, URLs, headers, bodies, paths and arbitrary extra
fields are omitted. Unknown SDK/server events become `diagnostic`, which
deliberately limits their troubleshooting detail to avoid secret leakage.
This protects Python logging records; it does not sanitize arbitrary direct
stdout/stderr writes from future dependencies.

The pure ASGI middleware generates a fresh `X-Request-ID` regardless of the
incoming header, logs status/duration for each HTTP request, and resets request
and run context on completion, failure or cancellation. Concurrent async work
inherits only its own request context. The formatter supports `run_id`,
`retrieval_attempts`, `token_usage` and `search_calls` for future agents/providers;
those counters are not measured by the health scaffold. Set/reset the `run_id`
context around future orchestration, and supply typed codes/numeric metrics via
logging `extra` rather than putting data into a message.

Offline observable contracts are in
[test_foundation.py](tests/unit/test_foundation.py). They cover dependency
replacement, fixed public failures, synthetic private-data redaction, SDK/server
logging, injected duration/IDs, cancellation and overlapping request contexts.
Run them from `backend/` with:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin tests/unit/test_foundation.py
```

`migrations/versions` contains the catalog and provenance Alembic revisions.
`tests/unit` contains the configuration and service-health contracts;
`tests/integration` contains real PostgreSQL/pgvector foundation checks;
`tests/contract` contains offline provider SDK and local model-fixture checks.

## Shared domain contracts (P02-01)

The [domain package](src/food_recommender/domain/) contains frozen standard-library
dataclasses and enums with no framework, provider or persistence imports.
Collections use tuples. Typed callers construct these objects directly; parse
untrusted JSON through the strict [application adapters](src/food_recommender/application/contracts.py).
The adapters preserve domain types, reject extra fields at every nested level,
and run the same domain invariants. Serialization alone does not validate data.

| Contract | Behavior |
| --- | --- |
| `Preferences`, `Constraint`, `ProfileResult` | Preserve explicit/inferred origin and hard/soft strength. An inferred restriction cannot become hard without explicit user evidence. Location and price band remain nullable; empty collections represent no recorded values. Profile clarification is explicit. |
| `EntityRef`, `CandidateEvidence`, `Citation` | Keep restaurant/recipe ID namespaces separate, require source-backed candidate evidence, retain modality scores/ranks and limitations, and distinguish imported/generated/source attribution. Catalog citations identify entity/source/record/document; web citations require HTTP(S) URLs and timezone-aware retrieval dates. Publication dates remain unknown when absent. |
| Six role results and `ExpertOutcome[T]` | Cover profile, retrieval, trend, style, nutrition and recommendation outputs. Discriminated success/unavailable/failure outcomes keep an empty successful retrieval separate from a dependency failure. Style and nutrition assessments preserve supported/conflicting/unknown states. Trend claims require dated web evidence and candidate associations. |
| `RetrievalResult`, `RecommendationResult` | Require unique category-qualified entities. Retrieval allows up to 20 candidates/category and one initial query plus two refinements. Recommendations allow up to five items/category; fewer or zero are valid. |
| `validate_recommendations` | Check recommendation and nutrition citation IDs against each retrieved candidate's evidence. Reject unknown entities and conflicts; with `hard_constraints=True`, missing/unknown compliance is rejected. The caller supplies authoritative nutrition assessments. |
| Five event types | Define `progress`, `clarification`, `recommendations`, `error`, and terminal `done`, with UUID conversation/run IDs. Progress contains a role and activity; errors use fixed codes without exception details. |

Use `profile_adapter`, the six `*_outcome_adapter` objects, or `event_adapter`
for `validate_json()` and `dump_json()`. Use `contract_json_schema(adapter)` to
generate a schema that marks nested dataclasses with `additionalProperties: false`
and exposes the event/outcome discriminator. Schemas are derived from domain
fields rather than maintained as separate copies. For example:

```python
from food_recommender.application.contracts import profile_adapter

profile = profile_adapter.validate_json(
    '{"categories":["recipe"],"preferences":{"constraints":[]}}'
)
payload = profile_adapter.dump_json(profile)
```

This task defines and validates contracts. Ingredient classification, profile
merging across follow-ups, dated trend freshness/cache policy, expert orchestration,
evidence hydration for HTTP responses, SSE delivery/persistence and OpenAPI/frontend
generation remain later tasks. A citation or supported assessment is not dietary
certification; canonical ingredient checks must supply the restriction assessment.
For validation failures, omit inputs/context when inspecting structured Pydantic
errors, as described under configuration above.

From `backend/`, run the offline contracts with:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin tests/unit/test_domain_contracts.py
```

## Catalog persistence and migrations (P02-02)

The [catalog mappings](src/food_recommender/infrastructure/catalog.py) live in
infrastructure, outside the framework-independent domain package. Importing
them creates no engine or connection. The
[initial revision](migrations/versions/0001_catalog.py) creates `restaurants`,
`recipes` and `reviews`; no catalog data is imported or generated.

Each table requires an explicit string primary key and a unique
`(source_id, source_record_id)` pair. The table supplies the entity type, so
restaurant `"1"` and recipe `"1"` can coexist. Preserve legacy IDs as strings.
New entities need caller-assigned collision-free identities, rather than IDs
derived from row counts. `source_id` denotes the logical dataset; base and
augmented files belonging to that dataset share its identity. File/URL/hash
provenance is described below; merge adapters arrive in Phase 3.

Review `restaurant_id` references only `restaurants.id`. PostgreSQL rejects
missing targets and blocks deletion or ID changes while reviews reference a
restaurant. `demo_profile_id` preserves the synthetic review user's source ID;
profile/session ownership persistence arrives in P02-06. No ORM delete cascade
or relationship loading is introduced here.

Names, raw cuisine/location values and recipe time strings are retained alongside
nullable normalized filters. Ratings are source catalog values in the range
0–5, and price bands are 1–4. Unknown vibe, coordinates, difficulty, availability,
nutrition, ingredients and allergen evidence remain SQL `NULL`, without defaults.
Ordered ingredients/directions use text arrays. A null array differs from an
explicit empty array; neither supplies dietary certification. Assign a new
array or JSON value when updating these fields; in-place mutation tracking is
not configured. Source attribution, dietary checks and validated writes remain
later tasks.

From `backend/`, preview the migration without a database connection:

```bash
uv run --locked alembic upgrade head --sql
```

To apply it, explicitly export `DATABASE_URL` for the intended PostgreSQL
database, then run:

```bash
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked alembic check
```

The [migration environment](migrations/env.py) accepts `postgresql://` or
`postgresql+psycopg://`, reads no dotenv file and needs no Groq/Tavily/admin
configuration. Migrations are explicit operations; application startup does not
run them. These commands currently run from the host checkout; the existing
backend container does not package the Alembic files. The migration template
supports later revisions without dynamically rebuilding schema from current
models. `alembic downgrade base` removes the catalog tables and their data; use
that rollback command only on a disposable database for verification.

The [catalog integration tests](tests/integration/test_catalog_models.py) use
the existing limited disposable `foodwise_test` role. Each test runs migrations
and writes inside a transaction that rolls back. They check schema/model parity,
upgrade/downgrade/re-upgrade, duplicate canonical/source IDs, foreign keys,
nullable metadata, collection roundtrips and database value constraints.
[Offline entry-point tests](tests/unit/test_catalog_migrations.py) verify SQL
previews and explicit PostgreSQL configuration. With `TEST_DATABASE_URL` set as
in the [CI reproduction guide](../infra/ci.md#reproduce-the-database-and-model-checks-locally),
run:

```bash
make test-integration
```

Vector/full-text storage, conversation persistence,
repositories, optimistic versions and application transaction boundaries remain
P02-04 onward. P02-02 does not satisfy the Phase 2 exit gate.

## Source, document and media provenance (P02-03)

The [provenance mappings](src/food_recommender/infrastructure/provenance.py) extend
the catalog metadata. Import this module to register all seven tables; imports
perform no database or filesystem I/O. The
[second revision](migrations/versions/0002_provenance.py) adds four empty tables
without modifying existing catalog rows. The migration commands above apply
both revisions. `alembic downgrade 0001_catalog` removes only provenance tables
and their data; verify rollback only on a disposable database.

| Table | Provenance contract |
| --- | --- |
| `sources` | A caller-assigned artifact ID, logical dataset ID, file/URL/admin locator, SHA-256 content hash, creation time, optional publication date and retrieval time. The logical dataset/locator kind/locator/hash tuple is unique, so changed file contents form a separate revision. |
| `source_records` | Unique artifact/type/original-record identity, raw JSON payload and/or verbatim text, content hash, ingestion version and attribution. Optional restaurant/recipe/review foreign keys link at most one entity of the declared type; all-null links preserve unresolved input. |
| `documents` | Source-record reference, kind, text, hash, ingestion version, attribution and optional half-open offsets in the parent text used for chunking. Optional media links must refer to the same source record. |
| `media` | Source-record reference, unique private storage basename, optional original filename/URL, JPEG/PNG/WebP MIME type, positive byte size and dimensions, hash, ingestion version and attribution. Identical bytes can retain separate entity associations. |

Catalog `source_id` means the logical dataset; `source_records.source_id` means
the physical artifact row. A base JSON file and its augmented file have separate
artifact/record rows that can link to the same canonical entity, preserving both
raw payloads without duplicating that entity. Record IDs retain their original
source namespace. Reviewed mappings and ingestion adapters must choose the
correct entity association; foreign keys validate existence and entity type,
not whether an image actually depicts that entity.

Hashes are lowercase, 64-character SHA-256 hex strings. Database checks enforce
their format; Phase 3 ingestion computes/verifies their contents. `created_at`
defaults to the database transaction timestamp; all timestamp columns use
timezone-aware PostgreSQL storage. Unknown publication/retrieval dates remain
SQL `NULL`. Treat content revisions as append-only in ingestion; the schema
does not make rows immutable. Assign new JSON values when updating raw payloads.

Records, documents and media require explicit `source`, `imported` or `generated`
attribution. New generated content requires a nonblank generator identity and
input hash; generator revision stays nullable when unavailable. The ingestion
version identifies the processing code/prompt version. Imported course captions
can retain unknown generator details and must remain attributed as imported;
caption text does not establish observed ingredients or allergen compliance.

Foreign keys restrict parent deletion and ID changes. Application transactions
must explicitly remove dependent documents/media before their source records.
Storage keys contain no directory separators and are internal references, not
public URLs. This revision stores catalog media metadata; file decoding, upload
limits, storage operations, session ownership and conversation cleanup remain
Phase 3/P02-06/P02-09 work. Document construction and token-aware chunking remain
Phase 4 work; ingestion must validate offsets against the actual parent text.
Vectors, full-text indexes, repositories and validated CRUD remain later tasks.

[Real PostgreSQL provenance contracts](tests/integration/test_provenance_models.py)
cover base/augmented/revised artifacts, unresolved raw text, type namespaces,
generated/imported attribution, dates/hashes, duplicate rejection, invalid
values, cross-record media links, restrictive foreign keys, partial-write
rollback and catalog-preserving upgrade/downgrade/re-upgrade. The
[shared fixture](tests/integration/conftest.py) migrates and writes inside a
rolled-back transaction. Run `make test-integration` with the disposable
`TEST_DATABASE_URL` from the [CI guide](../infra/ci.md#reproduce-the-database-and-model-checks-locally).
Offline migration tests also preview both upgrade and downgrade without a
database or provider configuration. P02-03 does not satisfy the Phase 2 exit gate.

## Quality scripts (P01-06)

Run these commands from **`backend/`**, after `uv sync --locked`. The default
sync installs the locked `dev` dependency group: Ruff 0.16.10, mypy 2.4.0,
pytest 9.1.1 and pytest-asyncio 1.4.0. Production images use `--no-dev`.
The [Makefile](Makefile) requires GNU Make; each target also shows its direct
`uv run --locked` command, usable without Make.

| Command | Check or action |
| --- | --- |
| `make lint` | Ruff lint on `src`, `tests`, `scripts` and `migrations`, including imports and Python 3.12 syntax. |
| `make format-check` | Check Ruff formatting without changing files. |
| `make format` | Apply Ruff formatting to `src`, `tests`, `scripts` and `migrations`. |
| `make typecheck` | Strict mypy on all runtime packages, with Pydantic's plugin. |
| `make test` | Discover all tests under `tests`, including unittest and explicit async tests. |
| `make check` | Run lint, formatting check, typecheck and tests; fail on the first failed target. |
| `make test-integration` | Run real database contracts; requires the disposable `TEST_DATABASE_URL`. |
| `make provision-test-models` | Generate seeded local CPU fixtures; requires an ignored `TEST_MODEL_ROOT`. |

For a focused test without Make, run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin tests/unit/test_service_health.py
```

The test target disables automatic third-party pytest plugins and explicitly
loads pytest-asyncio, avoiding unrelated provider/telemetry plugins installed
with runtime SDKs. Async tests use `@pytest.mark.asyncio`; async fixtures should
use `@pytest_asyncio.fixture`. Strict mode and function-scoped event loops keep
each test independent. Unknown pytest settings and markers are errors.
See the [pytest-asyncio configuration reference](https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html).

Unit/provider contracts need no `.env`, database, MCP process, paid provider
calls or pretrained weights. HTTP contracts use in-process ASGI transports,
fake SDK responses and injected/mocked readiness boundaries. The PostgreSQL
and seeded-model suites run when their test settings are supplied; otherwise
ordinary local runs skip them explicitly. CI requires both and rejects missing
settings. See the [CI guide](../infra/ci.md) for the complete disposable-database
setup, local fixture provisioning, checks and cleanup. These foundation tests
do not establish application retrieval or recommendation behavior.

## Embedding storage (P02-04)

Revision `0003_embeddings` runs `CREATE EXTENSION IF NOT EXISTS vector` and
creates separate `text_embeddings` (`vector(384)`, MiniLM) and
`image_embeddings` (`vector(512)`, CLIP) tables. Each row records a nonblank
model revision, input SHA-256, dimension and creation time. Database checks
require unit vectors (tolerance 0.001) and the configured model identity.
Document/media deletion cascades to its vectors; the extension survives downgrade
because other applications may use it. A database administrator must preinstall
pgvector for a limited role, as the Compose/bootstrap scripts already do. Exact
cosine search remains the baseline; embedding generation and retrieval services
are Phase 4/5 work.

## Search schema (P02-05)

Revision `0004_search` adds a stored English `documents.search_vector` computed
from its complete text on every write and a GIN index. Ordinary B-tree indexes
cover normalized restaurant cuisine/location/price, location/price alone, recipe
cuisine, profile-scoped reviews and document/media/entity links. No approximate
vector index is created. Phase 4 builds the source-backed documents and query
services over these fields.

## Conversations, profiles, trends and checkpoints (P02-06)

Revision `0005_context` adds UUID conversations tied to hashed-token browser
sessions, messages, conversation-specific preferences and synthetic demo
profiles. Legacy review profile IDs are backfilled before adding the foreign
key. Catalog media retain source provenance; uploaded media instead require an
owner session. Composite foreign keys limit conversation/upload links to the
same session and permit sharing between that session's conversations. Media
files and browser cookie handling are later application work.

Trend cache rows store sanitized culinary queries/hashes, retrieval/expiry
timestamps (maximum 24 hours), and up to five evidence records with excerpts,
actual URLs and nullable publication dates. Unknown dates remain unknown;
current-trend eligibility and query sanitization are Phase 6 services.

Alembic owns application tables. LangGraph owns its tables in the separate
`foodwise_checkpoints` schema through the supported
[PostgreSQL saver setup](https://docs.langchain.com/oss/python/langgraph/persistence).
New Compose/test databases create that schema during administrator bootstrap.
For an existing application database, an administrator must first execute
`CREATE SCHEMA foodwise_checkpoints AUTHORIZATION foodwise;`. Do not drop
existing volumes to rerun bootstrap. Then, from `backend/` with an explicitly
selected `DATABASE_URL`, run:

```bash
uv run --locked alembic upgrade head
uv run --locked python scripts/setup_checkpoints.py
```

Setup is idempotent and uses autocommit for LangGraph's concurrent indexes.
Ordinary factories and runtime saver opening never migrate. Use the conversation
UUID string as the checkpoint thread ID. Checkpoint access is internal; future
graph services must first authorize the session/conversation. Application
downgrades retain library checkpoint tables. Downgrading below P02-06 while
uploads exist is rejected instead of discarding upload data.

## Repository transactions and optimistic versions (P02-07)

Application [ports](src/food_recommender/application/ports.py) expose domain
snapshots, conversation context and dated trend records.
[Prepared catalog bundles](src/food_recommender/domain/catalog.py) check hashes,
source/media associations, model compatibility, dimensions and normalization
before the final transaction. Prepare full content and vectors outside the
transaction; never call inference inside a write.

[CatalogService](src/food_recommender/application/persistence.py) uses an injected
unit-of-work factory. The async PostgreSQL adapter commits canonical data,
source/raw provenance, documents, media and vectors together. Revision
`0006_versions` adds positive versions; replace/delete use conditional writes
with `expected_version`. Missing IDs, stale versions, duplicate identities and
invalid foreign keys return typed failures. Raw source revisions survive updates
and become unresolved on deletion. Restaurant deletion with linked reviews
fails atomically. Source identity changes require reconciliation, not mutation.

`PostgresUnitOfWork` rolls back by default; only explicit `commit()` persists.
Exceptions and cancellation preserve old data. Read transactions also close
without writes. Conversation/profile/message/media methods require the owner
session and authorize before access. A profile save is a complete supplied
snapshot; Phase 7 supplies follow-up merging rules. Trend reads exclude expired
or future cache entries; publication-date eligibility remains Phase 6. Backend
composition exposes `Services.transactions`, constructs no database connections
until use and disposes its pool at shutdown. Routes are Phase 8 work.

## Persistence integrity acceptance (P02-08)

[Integrity tests](tests/integration/test_persistence_integrity.py) run against
the disposable real PostgreSQL database, including two separate pooled
connections competing for one expected version. Exactly one update commits.
Failed replacements/foreign-key deletes and cancellation preserve complete
previous data; duplicate IDs cannot create partial provenance/retrieval rows.
Additional checks exercise upgrade of legacy synthetic profiles, session-scoped
reads/writes, explicit-restriction roundtrips, cache expiry boundaries and failed
cache refreshes. Existing suites cover fresh downgrade/upgrade/schema parity,
nullable unknowns, source/media identity and normalized vector constraints.

Run `make test-integration` with the documented `TEST_DATABASE_URL`. Tests
require `foodwise_test` on loopback and never use the application database.
The concurrency contract commits only its uniquely named fixture record and
cleans it afterward; migrations are committed to the disposable test database.
