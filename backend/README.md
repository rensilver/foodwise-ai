# Backend scaffold

The application package is `src/food_recommender`. P01-03 adds validated
configuration in the infrastructure package. P01-05 adds FastAPI and FastMCP
startup factories and local health probes; the domain/application/agent and
retrieval packages remain scaffolds. P01-02 pins Python 3.12.14 in
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

Settings are immutable and loaded afresh on each call. Startup can load them
once and inject them into adapters when the composition roots are implemented.
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

`migrations/versions` reserves the Alembic revision location for Phase 2.
`tests/unit` contains the configuration and service-health contracts;
`tests/integration` and `tests/contract` reserve later suites.

## Quality scripts (P01-06)

Run these commands from **`backend/`**, after `uv sync --locked`. The default
sync installs the locked `dev` dependency group: Ruff 0.16.10, mypy 2.4.0,
pytest 9.1.1 and pytest-asyncio 1.4.0. Production images use `--no-dev`.
The [Makefile](Makefile) requires GNU Make; each target also shows its direct
`uv run --locked` command, usable without Make.

| Command | Check or action |
| --- | --- |
| `make lint` | Ruff lint on `src` and `tests`, including imports and Python 3.12 syntax. |
| `make format-check` | Check Ruff formatting without changing files. |
| `make format` | Apply Ruff formatting to `src` and `tests`. |
| `make typecheck` | Strict mypy on all runtime packages, with Pydantic's plugin. |
| `make test` | Discover all tests under `tests`, including unittest and explicit async tests. |
| `make check` | Run lint, formatting check, typecheck and tests; fail on the first failed target. |

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

Current tests need no `.env`, database, MCP process, Groq/Tavily calls or model
weights. HTTP contracts use in-process ASGI transports and injected/mocked
readiness boundaries. Real database tests and CI remain P01-07; this suite
does not establish real PostgreSQL retrieval or recommendation behavior.
