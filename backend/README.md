# Backend scaffold

The application package is `src/food_recommender`. P01-03 adds validated
configuration in the infrastructure package; the other packages still contain
only docstrings. P01-02 pins Python 3.12.14 in
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

Service startup, migrations, and quality scripts remain pending
their checklist tasks. Framework imports do not establish application readiness.

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
The example's PostgreSQL and MCP endpoints describe future host-run services;
they do not start them. Add URL-encoded database credentials when required and
select your absolute media directory. Compose hostnames and mounted media
configuration arrive in P01-05.

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

Run the offline configuration contracts from `backend/` after locked installation:

```bash
uv run --locked python -m unittest discover -s tests/unit -p 'test_config.py' -v
```

These tests use synthetic credentials and temporary dotenv files. They use the
standard library test runner until the pytest/quality scripts arrive in P01-06;
pytest can also collect the unittest cases later.

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
`tests/unit` contains the configuration contracts; `tests/integration` and
`tests/contract` reserve later suites. Shared test tooling and scripts remain
scheduled in P01-06.
