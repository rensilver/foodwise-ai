# foodwise-ai backend

Package responsibilities, dependency rules and CLI path changes are documented in
[Package organization](PACKAGES.md).

The application package is `src/food_recommender`. P01-03 adds validated
configuration in the infrastructure package. P01-05 adds FastAPI and FastMCP
startup factories and local health probes. P01-08 adds composition roots,
application readiness dependencies, typed failures and structured logging.
Phase 2 adds shared domain contracts, catalog/provenance/vector/context
migrations, async transactional repositories, optimistic versions, supported
LangGraph checkpoints and retryable conversation/media deletion. Phase 3 adds
validated ingestion/media; Phases 4–6 add cited multimodal retrieval and MCP.
Phase 7 implements six-agent execution; Phase 8 adds owned HTTP/SSE and catalog
administration. Live graph acceptance is blocked by Groq token limits. P01-02 pins Python 3.12.14 in
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
| `MINILM_ROOT` | Optional absolute path to the provisioned pinned MiniLM bundle. Required for admin writes and backend readiness; no automatic download. Compose mounts it read-only. |
| `ALLOWED_ORIGINS` | Optional JSON array of permitted browser origins. Defaults to localhost/127.0.0.1 with ports 3000/8000, plus `http://localhost`. Administrator requests must provide an allowed `Origin`. |

The administrator hash policy accepts memory costs of 19,456–262,144 KiB,
2–10 iterations and 1–16 parallel lanes, with a 16–64 byte salt and a 32–64
byte digest in canonical unpadded base64. Its minimum costs follow the
[OWASP Argon2id guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#argon2id).
Validation checks encoding and bounded costs. Generate a unique password hash
locally with an Argon2id PHC-capable tool using those costs and keep the password
separate. Phase 8 verifies passwords off the event loop and stores revocable
administrator sessions. This project does not ship a default administrator password.

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
shared [HTTP boundary](src/food_recommender/transport/http.py) returns
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

The contracts now support deterministic ingredient checks, retained follow-up
restrictions, dated trend evidence and six-role orchestration. Evidence hydration
for HTTP responses, SSE delivery/persistence and OpenAPI/frontend generation
remain later tasks. A citation or supported assessment is not dietary
certification; canonical ingredient checks must supply the restriction assessment.
For validation failures, omit inputs/context when inspecting structured Pydantic
errors, as described under configuration above.

From `backend/`, run the offline contracts with:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --locked pytest -p pytest_asyncio.plugin tests/unit/test_domain_contracts.py
```

## Catalog persistence and migrations (P02-02)

The [catalog mappings](src/food_recommender/infrastructure/persistence/models/catalog.py) live in
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

P02-04 through P02-09 extend this foundation with vector/full-text storage,
conversation persistence, repositories, optimistic versions and deletion; see
the sections below and the verified Phase 2 exit gate in the checklist.

## Source, document and media provenance (P02-03)

The [provenance mappings](src/food_recommender/infrastructure/persistence/models/provenance.py) extend
the catalog metadata. The migration environment imports
`infrastructure.cleanup` to register the complete application metadata; imports
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
limits and upload storage remain Phase 3/8 work. P02-06/P02-09 below add session
ownership, conversation cleanup and safe file deletion. Document construction and token-aware chunking remain
Phase 4 work; ingestion must validate offsets against the actual parent text.
P02-04 through P02-09 below implement vector/full-text storage and transactional
repositories. Phase 8 exposes validated CRUD through shared application use cases.

[Real PostgreSQL provenance contracts](tests/integration/test_provenance_models.py)
cover base/augmented/revised artifacts, unresolved raw text, type namespaces,
generated/imported attribution, dates/hashes, duplicate rejection, invalid
values, cross-record media links, restrictive foreign keys, partial-write
rollback and catalog-preserving upgrade/downgrade/re-upgrade. The
[shared fixture](tests/integration/conftest.py) migrates and writes inside a
rolled-back transaction. Run `make test-integration` with the disposable
`TEST_DATABASE_URL` from the [CI guide](../infra/ci.md#reproduce-the-database-and-model-checks-locally).
Offline migration tests also preview upgrades and downgrades without a
database or provider configuration. The complete Phase 2 exit gate is recorded
in the checklist.

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
| `make check` | Run lint, formatting check, typecheck, OpenAPI drift check and tests; fail on the first failed target. |
| `make api-schema` | Export deterministic OpenAPI without contacting dependencies. Regenerate frontend types afterward. |
| `make api-schema-check` | Reject drift between the current API and the committed OpenAPI. |
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

[CatalogService](src/food_recommender/application/catalog.py) uses an injected
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
until use and disposes its pool at shutdown. Phase 8 routers use injected services.

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

## Conversation erasure and media cleanup (P02-09)

`ConversationService.delete(session_id, conversation_id)` authorizes and locks
its owner conversation. One transaction removes messages, profile context,
media associations and all LangGraph checkpoints/blobs/pending writes through
the supported saver's `adelete_thread()` on the same psycopg connection. Failure
rolls back all database deletion. Use the UUID conversation string as the graph
thread ID. Future graph services must coordinate active-run exclusion and
cancellation before deletion (P07-11); HTTP ownership/cookies are P08-01.

Uploads referenced by another owner conversation remain. Unshared uploads and
their image vectors are deleted; shared catalog data, provenance and other
sessions survive. Revision `0007_cleanup` adds a durable file-cleanup outbox,
also populated by catalog replacements/deletes. After committing database
changes, the injected cleanup service removes unreferenced private files by
validated basename. It uses descriptor-relative unlink, refuses a symlinked
mount root and removes file symlinks themselves rather than their targets.
Missing files are idempotent success; storage still referenced by media is kept.
Failed removal stays queued and conversation deletion exposes `cleanup_pending`.

Backend composition wires the services and a local media adapter. To retry one
bounded batch (up to 100 jobs), explicitly select `DATABASE_URL` and `MEDIA_ROOT`
and run from `backend/`:

```bash
uv run --locked python scripts/cleanup_media.py
```

The command emits only removed/retained/failed counts and exits nonzero if file
cleanup fails. Repeat it to drain additional batches. It does not read dotenv
files, initialize tables, decode uploads or call providers. Media filenames must
be generated and immutable in the future upload/ingestion services.

[Deletion tests](tests/integration/test_conversation_deletion.py) use real saver
checkpoints, raw blobs, pending writes, database transactions and filesystem
fixtures. They verify post-delete rollback, checkpoint failure rollback,
unauthorized deletion, shared-upload lifetime, unrelated catalog preservation,
retryable file failures and committed erasure after reopening connections.
[Filesystem tests](tests/unit/test_media_cleanup.py) reject caller paths and
symlinked roots. Phase 2 establishes persistence contracts; ingestion, retrieval,
agent scheduling and the user/admin HTTP journeys remain their later phases.

## Seed ingestion (Phase 3)

Run imports explicitly after `uv run --locked alembic upgrade head`, from
`backend/`. Imports use `DATABASE_URL` and an absolute `MEDIA_ROOT`; they do not
require or call Groq/Tavily. An explicit `--env-file` before the subcommand can
load local configuration without printing it. Environment values take precedence.

```bash
uv run --locked python -m food_recommender.cli.ingestion import
```

The default inputs are the five committed JSON artifacts, raw culinary map,
Phase 0 paragraph mapping, and separately recovered recipe ZIP. Use
`--data-root`, `--mapping`, `--accepted`, `--corrections`, `--recipe-zip`, `--media-root`, and
`--report` to select explicit local inputs. `--download-review-images` permits
bounded downloads from the approved course host; otherwise only previously
cached review images are used and missing imagery is reported. Recover the ZIP
separately on clean checkouts; the placeholder image is never substituted.

The ignored `.local-tmp/ingestion/manifest.json` records every entity's hash,
status, media provenance, source hashes, paragraph mappings and unresolved
items. `downloads/` beside the report caches course images. Storage keys are
private generated basenames; source IDs and raw payloads remain in PostgreSQL.
Caption text is imported enrichment, not proof of ingredients or dietary safety.
Recipe durations use ISO minute strings while retaining original raw strings.
The committed acceptance ledger adds six source-backed restaurants with stable UUIDs. The correction ledger maps the unsupported legacy band 5 for `1000003` to band 4 using the hash-verified raw paragraph; the original value remains in provenance. Invalid or stale correction evidence is rejected. Other unsupported values remain unknown and reported.

Each item and its ingestion checkpoint commit atomically. Rerun the same command
after interruption: committed items become `unchanged`, pending items resume,
and changed items advance their version. Source revisions remain traceable;
only stale retrieval rows for changed entities are invalidated. Administrator
edits and deletions conflict rather than being overwritten or resurrected. Removed media enters the existing
durable cleanup queue. No startup import, table wipe, or global index reset is
performed. A completed import may still contain reported unresolved items;
rejected items or configuration/dependency failures exit with status 2.

For a provider-backed administrator preview, explicitly enable Groq by supplying
a fresh key and the configured model, then write the result to ignored storage:

```bash
uv run --locked python -m food_recommender.cli.ingestion preview \
  --category restaurant --input /absolute/path/description.txt \
  --output ../.local-tmp/ingestion/preview.json
```

A preview validates fields without catalog writes. Import extraction services
allow two repairs and quarantine invalid output with source references. Vision
inference has a separate injected model and content/model/version cache; supplied
captions bypass inference. The configured model never changes automatically.
The adapter follows [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
and [vision input guidance](https://console.groq.com/docs/vision); live capability
checks remain explicit opt-in work, independent of offline ingestion tests.

## Multi-source text retrieval (Phase 4)

`food_recommender.retrieval` now provides real restaurant/recipe/scoped-review
retrieval without inference-generated candidates. Indexing is an explicit local
operation after migrations and Phase 3 ingestion. Startup does not download models
or rebuild indexes. Select your intended database via `DATABASE_URL`; commands do
not load dotenv files. No Groq/Tavily credentials are needed.

From `backend/`, provision the pinned public Apache-2.0 MiniLM weights once:

```bash
export MINILM_ROOT="$(realpath ../.local-tmp)/minilm"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_PROGRESS_BARS=1
make provision-minilm
make index-text
uv run --locked python -m food_recommender.cli.text --model-root "$MINILM_ROOT" search "tomato basil pizza" --category recipe --source recipe --cuisine Italian
uv run --locked python -m food_recommender.cli.text --model-root "$MINILM_ROOT" search "cozy greenhouse" --category restaurant --source restaurant --location "Silver Lake" --max-price-band 4
```

Model provisioning requires public Hugging Face network access and writes only to
`MINILM_ROOT`. It pins `sentence-transformers/all-MiniLM-L6-v2` revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; the local manifest records file hashes.
Loading is offline with CPU, disabled remote code, 384 dimensions and normalized
vectors. Neither the random CI fixtures nor CLIP can substitute for this model.
[The model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
and [encoder documentation](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
explain the encoder's token limit and normalization options.

Documents project immutable culinary records and retain source/record identity.
Paragraph offsets address the raw paragraph; structured offsets address the
projection reconstructed by `retrieval.documents.render`. Caption offsets address
the original attributed caption identified by its document kind. Chunks stay
within the tokenizer budget including special tokens and preserve character ranges;
canonical ingredient arrays remain complete. Imported/generated captions retain
attribution, generator metadata and media links and do not establish ingredients.

Indexing skips existing model/revision/input hashes and commits bounded prepared
batches. It removes only obsolete Phase 4 projections after replacement succeeds.
An interrupted import is safely resumable. An unchanged full-corpus rerun encodes
zero documents. Missing or incompatible dense rows produce `dependency_error`
until indexing completes. Original source records/media/catalog versions remain.

`TextPlan` accepts query, requested categories/sources, exact cuisine/location/name,
maximum restaurant price band, entity IDs, explicit review-profile scope, constraints
and a limit of 1–20 per category. `TextRetrieval.run` returns the shared typed
`TextRetrievalOutcome` contract; `text_retrieval_adapter` serializes and validates it.
`Constraint` values can be supplied by application callers to distinguish soft
preferences from hard allergens/diets. Restaurants have no verified ingredient
composition, and no course item supplies verified allergen-absence evidence. Hard
allergies therefore abstain; known conflicts always exclude, and unsupported or
ambiguous diets stay unknown. Strict vegan/vegetarian composition is supported
only for complete lists of explicitly recognized simple plant ingredients. No
assessment guarantees cross-contact safety or measured nutrition.

Full-text and exact cosine branches share parameterized filters. Restaurant fields
never filter recipes. Review search requires `--source review --demo-profile-id`
and maps evidence to the actual reviewed restaurant. Review text/captions remain
excluded by default. Original scores and citation source/record/document IDs accompany
results. Entity ranks deduplicate chunks before equal-weight RRF (`k=60`), then
normalize within each category. Stable entity-ID ties and equal scores are explicit.
Internal document scans are exhaustive for the small corpus; the final response
contains at most 20 unique entities per category. No approximate index is used;
[pgvector's exact-search guidance](https://github.com/pgvector/pgvector) applies.

Outcomes distinguish success, no results, unavailable dependencies and invalid
requests. Database/provider exception messages are not returned; cancellation
propagates. Calls have a default 30-second deadline and one CPU encoding operation
at a time per service instance. Groq, trend search, image search, MCP wiring and
HTTP/frontend flows remain their later phases.

Run `make evaluate-text` on the full seeded and indexed corpus to reproduce the
[initial baseline](../evaluation/phase4/README.md). It overwrites the report, so
review changed hardware/timing evidence before committing. Normal CI continues to
use deterministic CPU adapters and the real PostgreSQL service. To additionally
run the downloaded pretrained contract without network access:

```bash
export TEST_MINILM_ROOT="$MINILM_ROOT"
make check
```

This optional pretrained contract skips only when `TEST_MINILM_ROOT` is absent;
a configured broken/missing model fails. All other Phase 4 tests use offline
fixtures and need no pretrained download.

## Multimodal retrieval (Phase 5)

The [Phase 5 report](../evaluation/phase5/README.md) records real CLIP indexing,
image queries, cited entity-level fusion and five measured weight settings.
Provision CLIP explicitly into ignored storage after seed media restoration:

```bash
export CLIP_ROOT="$(realpath ../.local-tmp)/clip"
make provision-clip
make index-images
make evaluate-multimodal
```

These targets use the selected `DATABASE_URL`, absolute `MEDIA_ROOT`, and
`MINILM_ROOT` for combined evaluation. `index-images` hashes actual bytes,
checks media associations, encodes normalized 512-dimensional vectors in
bounded CPU batches and commits each prepared batch atomically. Reruns skip
unchanged inference. Startup never downloads models or wipes vectors.

Search the shared multimodal service from `backend/`:

```bash
uv run --locked python -m food_recommender.cli.multimodal "tomato basil pizza" --minilm-root "$MINILM_ROOT" --clip-root "$CLIP_ROOT" --category recipe --source recipe
uv run --locked python -m food_recommender.cli.multimodal --clip-root "$CLIP_ROOT" --image-only --media-id "$CATALOG_MEDIA_ID" --session-id 00000000-0000-0000-0000-000000000001 --category recipe --source recipe
```

Set `CATALOG_MEDIA_ID` to a `media_ids` value returned by the first search.
The local CLI explicitly enables catalog-image query access. Application
composition defaults to session-owned query images; its trusted caller supplies
the session ID. Neither entry point accepts image paths or URLs. Text/image
weights default to `0.6/0.4`; `--text-weight`/`--image-weight` select experiments.
`--cuisine`, `--location`, `--max-price-band`, `--entity-id`, `--hard-allergen`
and explicit `--source review --demo-profile-id` reuse shared constraints/scope.
Restaurant-only filters never apply to recipes. `--limit` is 1..20 per category.

Results retain canonical ingredients, raw/normalized component scores, effective
per-category weights, media IDs and association citations. Relevance is not
confidence or dietary certification. Empty/missing modalities renormalize
active weights and report limitations. Unauthorized query images abort; a
missing index cannot masquerade as a genuine empty search. Images do not prove
allergen absence, and unknown hard restrictions remain excluded. Static decoded
JPEG/PNG/WebP inputs are bounded at 10 MiB and 20 megapixels. HTTP uploads and
browser sessions are enforced by Phase 8 HTTP use cases.

For offline pretrained contracts, set `TEST_CLIP_ROOT="$CLIP_ROOT"` alongside
`TEST_MINILM_ROOT="$MINILM_ROOT"` and the existing disposable test settings.
Normal CI uses fake encoders for behavior and separately provisioned seeded
fixtures; it does not download CLIP weights during tests.

## MCP services and live trends (Phase 6)

MCP now exposes shared catalog lookups, constrained restaurant/recipe/image
retrieval and bounded Tavily trends, plus `foodwise://culinary-map`,
`foodwise://dataset-manifest` and `foodwise://source-provenance`. All tools are
read-only to agents; only the public search cache may be written internally.
Resources contain public catalog projections, excluding reviews and session data.

Host HTTP startup remains:

```bash
uv run --locked uvicorn food_recommender.mcp.server:create_app --factory --env-file ../.env --host 127.0.0.1 --port 8001 --no-access-log
```

The same server supports a stdio demo:

```bash
uv run --locked python -m food_recommender.mcp.server --transport stdio --env-file ../.env
```

Logs go to stderr; stdout is reserved for protocol traffic. Supply the intended
local `DATABASE_URL` and `MEDIA_ROOT`. Set optional `MINILM_ROOT`/`CLIP_ROOT` only
when the pinned pretrained models are provisioned. Omitted models produce typed
dependency outcomes. Models load on the first off-loop query; health/discovery
load none. Compose mounts provisioned models and media read-only into its internal
MCP service. Migrations, ingestion and model provisioning remain explicit.

At application startup, create one `configured_client(settings)` and hold its
context open. `AgentMCP` views reuse it across calls and apply the six fixed role
allowlists, discovered JSON schemas, domain result validation and injected scope.
Only application configuration chooses the server; models cannot provide URLs,
paths, SQL, mutation tools or new capabilities. No sampling callback is required.

Trend requests accept one to three approved concepts and California, United States
or global geography; arbitrary profile/review/restriction text is rejected.
Application-issued run IDs share the two-request budget across retries and
connections in one MCP process. The single-process Compose server is the supported
runtime; multiple replicas would require shared run-budget coordination.
Tavily news/basic requests return at most five items. Cache TTL is 24 hours;
publication freshness is 90 days, revalidated when reading and citing evidence.
Missing/unknown/stale evidence, credentials, cache failures and provider failures
return explicit unavailable outcomes. Groq analysis stays in the application.

Use `make verify-mcp-catalog` with a seeded database and provisioned models for
both real transports. The live command requires deliberate opt-in:

```bash
ENABLE_LIVE_TAVILY=1 make smoke-food-trends
```

It selects the root `.env`, uses its fresh Tavily key, and may spend at most two
requests. Offline tests remain independent. See the
[Phase 6 evidence and limitations](../evaluation/phase6/README.md) for reports.

## Phase 7 six-agent workflow

`composition.build_workflow_roles(inference, rag_tools, trend_tools)` constructs
six roles over injected ports. `agents.graph.build_graph` runs profile and RAG
sequentially, fans out trend/style/nutrition asynchronously, and joins all three
outcomes before one synthesis. Expert batches cover up to 20 candidates per
category; source-backed canonical ingredients remain authoritative. Synthesis
validates IDs, each candidate's citations and source excerpts, with one repair.
Explanations and style observations currently use source excerpts to prevent
unsupported generated claims. This is deliberately narrower than unconstrained
natural-language reasoning.

`agents.runner.GraphRunner` uses opaque UUID threads with an injected owned-run
lease. Production wiring uses `PostgresConversationRuns` and `checkpoint_saver`;
run the supported checkpoint setup explicitly after schema provisioning. One
active turn is allowed per conversation, including across processes. Read/history
never invokes the graph. Cancellation persists a terminal marker; the next turn
requires an explicit `TurnRequest`. Checkpoints retain profile/history while
control nodes clear transient results before every new turn. An omitted restriction
is retained; explicit field corrections or evidence-backed removals can change it.
Contradictory changes request clarification.

Defaults in `application.reliability.RunLimits` are 30 seconds/call, 120 seconds/run,
two transient transport retries, two schema repairs and three simultaneous Groq
calls. Use a shared process semaphore/provider. Repairs, retries and batches share
the same run deadline. Output state records safe stage timing and call/token/search
usage; logs omit prompts, catalog/private context, response bodies and credentials.
Groq structured requests never combine tools or streaming, following the
[official structured-output contract](https://console.groq.com/docs/structured-outputs).
[Vision documentation](https://console.groq.com/docs/vision) and the opt-in capability
probe verify the independently configured models without fallback.

Phase 8 exposes the graph through POST/SSE with browser ownership, persistence and
disconnect cancellation. Browser presentation remains Phase 9 work.

The opt-in commands are `ENABLE_LIVE_GROQ=1 make check-groq-capabilities` and
`ENABLE_LIVE_GRAPH=1 make smoke-agent-graph`. The graph target sends synthetic
catalog evidence to Groq and fixed public culinary concepts to Tavily. Supply
`GRAPH_SERVICE_ENV_FILE=/absolute/path/to/private-services.env` when database,
media and model settings are in a separate ignored file. These commands are
independent of `make check`; see the [Phase 7 report](../evaluation/phase7/README.md)
for actual results and the unresolved Groq HTTP 413 live-acceptance blocker.

## Phase 8 HTTP contract

The injected FastAPI factory serves `/api/v1`; `/openapi.json` exposes the
contract. Start it using the [developer workflow](../infra/development.md).
Run application migrations through `0009_admin`, initialize the supported
LangGraph checkpoint schema with the existing [checkpoint setup](#conversations-profiles-trends-and-checkpoints-p02-06),
restore/ingest local media and index the intended catalog. Provision the pinned
MiniLM bundle and set backend `MINILM_ROOT` before administrator writes. Compose
mounts this bundle read-only for both backend and MCP. Missing preparation
capabilities return `503` without changing catalog data.

| Endpoint under `/api/v1` | Behavior |
| --- | --- |
| `POST /conversations` | Create a conversation and, when needed, a local browser-session cookie. |
| `GET /conversations/{id}` | Return owned messages and preferences; never execute/resume the graph. |
| `DELETE /conversations/{id}` | Delete owned history, profile, checkpoints and unshared images; expose retryable `cleanup_pending`. Active runs receive `409`. |
| `POST /conversations/{id}/messages` | Validate and persist the request, then stream typed progress and final results. |
| `GET /restaurants`, `/recipes`; `GET /restaurants/{id}`, `/recipes/{id}` | Browse paginated synthetic catalog records and cited source details. |
| `POST /media`; `GET /media/{id}` | Upload a validated image or read a browser-owned image. |
| `POST /admin/session`; `DELETE /admin/session` | Authenticate the configured local administrator or revoke the session. |
| `POST /admin/extractions/preview` | Validate an unstructured restaurant/recipe description without persistence. |
| `POST /admin/restaurants`, `/admin/recipes` | Create records with server-issued IDs and prepared text retrieval data. |
| `PATCH`, `DELETE /admin/restaurants/{id}`, `/admin/recipes/{id}` | Update/delete with expected versions and explicit delete intent. |
| `GET /health/live`; `GET /health/ready` | Process health and dependency readiness without paid calls or model loading. |

Browser-session cookies are HttpOnly, SameSite Strict and scoped to `/`.
Only hashes of the opaque session tokens are stored. Ownership is independent
of administrator authority; wrong-owner conversations/images return `404`.
Keep cookies with requests. Supplied browser origins must be allowed by backend
`ALLOWED_ORIGINS`; cross-site requests are rejected. The default allowed hosts
are localhost, 127.0.0.1 and the internal Compose backend hostname.

Submit a message with JSON such as:

```json
{
  "message": "Suggest an Italian recipe",
  "client_request_id": "7291ed93-932f-4fe9-9609-6389a0f791e8"
}
```

The contract also accepts optional `explicit`, `categories`, `demo_profile_id` and
`media_id`; use the generated schema for exact constraints. Every intentional
new turn uses a fresh client UUID. A replayed UUID returns `409`, and only one
active turn is allowed per conversation across processes. Restrictions persist
through follow-ups unless explicitly corrected.

Use browser `fetch` for POST streams. Each SSE frame has an event name and JSON
data described by `StreamContract`: `progress`, `clarification`,
`recommendations`, `error`, or terminal `done`. Data includes conversation/run
IDs; cited recommendations include candidate evidence and expert outcomes.
Activity events show stage status without chain-of-thought. Comment heartbeats
arrive every 15 seconds while idle, with buffering disabled and no SSE replay ID.
The service commits validated final responses and profile changes before emitting
their payload. A disconnect cancels the producer/graph and releases the run lease.
Refetch history to discover whether completion was persisted; never
automatically resubmit a disconnected POST. Provider failures after headers use
typed `error`/`done` events without private details or stack traces.

Browse uses `limit` (1–100), `offset` (0–100000), `q` and `cuisine`;
restaurants additionally accept `location` and `max_price_band` (1–4).
Restaurant-only filters are rejected on recipes. Details retain unknown/null
catalog fields and source citations. Catalog data is explicitly labeled synthetic.

Upload multipart field `file` with decoded JPEG, PNG or WebP, at most 10 MiB and
20 megapixels. Animated, malformed and unsupported content is rejected. Images
are stored as metadata-free PNGs under generated private storage names; the
receipt supplies an opaque `id`, MIME type, dimensions and byte size. Use that ID in
message requests, never a path. Reads send `private, no-store` and `nosniff`.
Body middleware bounds chunked and declared-size uploads before multipart parsing.

Administrator login takes `{"password":"your local administrator password"}`
and requires an allowed `Origin`. Its response supplies `csrf_token` and
`expires_at`, and sets an HttpOnly SameSite Strict cookie scoped to `/api/v1/admin`.
Send `X-CSRF-Token` plus `Origin` on previews, writes and logout. Sessions expire
after eight hours; stored session/CSRF values are hashes, login replaces the old
session and logout revokes it. HTTPS sets Secure cookies; local HTTP uses the
loopback deployment. No default password is provided.

Preview takes `category` and `text`; returned validated fields require a separate
explicit create submission. Creates take `fields`; partial updates take `fields`
and `expected_version`. Immutable IDs/source identity are never client-editable.
Delete bodies require `expected_version` and `confirm_id` equal to the path ID.
Confirmed restaurant deletion also removes linked reviews and retrieval rows;
raw source payloads remain as provenance. Files with no remaining references are
queued for cleanup. Version conflicts return `409`. Text preparation happens
before the final transaction; catalog, documents and vectors commit together,
and failures preserve the prior record/version/retrieval data. Updates retain
existing media and image vectors.

Readiness checks database, writable media, MCP discovery, admin/checkpoint schema
presence and pinned encoder manifest/files. This does not verify Groq/Tavily
credentials or resolve the existing live graph token-limit blocker. Errors before
streaming use the shared structured error envelope and appropriate status
(`401`, `403`, `404`, `409`, `422`, `503`); validation responses omit submitted
secrets/content. See the [Phase 8 evidence](../evaluation/phase8/README.md).

For schema changes run `make api-schema` here, then `pnpm api:generate` from
`frontend/`. `make check` rejects OpenAPI drift; frontend `pnpm check` rejects
generated TypeScript drift. Export is offline and never reads owner credentials.
