# Backend scaffold

The application package is `src/food_recommender`. P01-03 adds validated
configuration in the infrastructure package. P01-05 adds FastAPI and FastMCP
startup factories and local health probes. P01-08 adds composition roots,
application readiness dependencies, typed failures and structured logging;
domain/agent/retrieval behavior remains planned. P01-02 pins Python 3.12.14 in
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
Migrations remain a later checklist task; quality scripts are documented below.
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

`migrations/versions` reserves the Alembic revision location for Phase 2.
`tests/unit` contains the configuration and service-health contracts;
`tests/integration` contains real PostgreSQL/pgvector foundation checks;
`tests/contract` contains offline provider SDK and local model-fixture checks.

## Quality scripts (P01-06)

Run these commands from **`backend/`**, after `uv sync --locked`. The default
sync installs the locked `dev` dependency group: Ruff 0.16.10, mypy 2.4.0,
pytest 9.1.1 and pytest-asyncio 1.4.0. Production images use `--no-dev`.
The [Makefile](Makefile) requires GNU Make; each target also shows its direct
`uv run --locked` command, usable without Make.

| Command | Check or action |
| --- | --- |
| `make lint` | Ruff lint on `src`, `tests` and `scripts`, including imports and Python 3.12 syntax. |
| `make format-check` | Check Ruff formatting without changing files. |
| `make format` | Apply Ruff formatting to `src`, `tests` and `scripts`. |
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
