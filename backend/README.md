# Backend scaffold

The application package is `src/food_recommender`. Its modules currently contain
only package docstrings. The project metadata declares the planned Python 3.12
requirement; the build backend, dependencies, runtime pin, and `uv.lock` belong
to P01-02. Installation and service commands are pending those tasks.

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
`tests/unit`, `tests/integration`, and `tests/contract` reserve the test suites;
test tooling and commands are scheduled in P01-06.
