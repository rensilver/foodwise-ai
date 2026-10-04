# Package organization

The backend separates culinary rules, use cases, concrete adapters and process
entrypoints. [AGENTS.md](../AGENTS.md) defines the project-wide rules;
[CHECKLIST.md](../CHECKLIST.md) tracks verification and later-phase work.

## Review and applied changes

The pre-Phase-7 review found four maintenance problems:

- Infrastructure mixed ORM mappings, repositories, encoders, providers, media
  handling and HTTP middleware in one directory. The 596-line persistence module
  owned engine construction, four repositories and transaction coordination.
- ORM registration depended on unrelated model imports and importing an ingestion
  store. Alembic had no explicit complete metadata entrypoint.
- Image retrieval imported validation from a concrete CLIP encoder. Text and
  image SQL search shared filters through the text-search adapter.
- CLI composition lived inside retrieval/ingestion packages, the course HTTP
  downloader lived alongside source-image preparation, and application catalog,
  conversation and cleanup services shared one persistence-named module.

The structure below addresses those boundaries while retaining the existing
algorithms, database schema, configured models and external API/MCP contracts.
The frontend remains a small scaffold; its existing App Router and feature
boundaries are appropriate for Phase 9.

## Backend map

```text
food_recommender/
  domain/                       # culinary entities, value types and invariants
  application/
    catalog.py                  # catalog use cases and transaction boundaries
    conversations.py            # owned conversation deletion and cleanup outcome
    media_cleanup.py            # bounded file-cleanup use case
    ports.py                    # repository/UoW/media contracts and snapshots
    lookups.py, trends.py        # lookup and trend use cases/ports
    resources.py                # public catalog resource port
    contracts.py, errors.py      # boundary validation and typed failures
    services.py                 # injected capabilities for process lifecycles
  retrieval/
    embedding_contracts.py      # supported model identities and vector validation
    ports.py                    # encoder/search/media boundaries
    ...                         # plans, evidence, fusion, chunking and services
  ingestion/                    # source adaptation, validation and import workflow
  agents/                       # Phase 7 graph state, nodes, prompts and controls
  infrastructure/
    persistence/
      models/                   # SQLAlchemy mappings only
        __init__.py             # explicit registry; exports complete Base metadata
        base.py, mixins.py       # declarative base and shared columns
        catalog.py, provenance.py, embeddings.py
        context.py, trends.py, cleanup.py, ingestion.py
      repositories/             # SQL-backed port implementations, grouped by use case
        catalog.py, conversations.py, trends.py, media_cleanup.py
        lookups.py, resources.py
      search/                   # PostgreSQL text/image queries and shared SQL filters
      indexing/                 # prepared document/vector writes for text/images
      engine.py                 # explicit engine factory
      unit_of_work.py            # one transaction shared by repositories
      checkpoints.py            # supported LangGraph saver lifecycle/setup
      ingestion.py              # atomic seed store
      query_media.py            # ownership checks using persisted media references
    embeddings/                 # local model execution: minilm.py, clip.py, lazy.py
    providers/                  # external inference/search: groq.py, tavily.py
    media/                      # files.py, images.py and approved-host downloads.py
    config.py, mcp_config.py     # explicit process settings
    health.py, observability.py  # cross-cutting operational adapters
  composition.py                # shared service construction and dependency injection
  api/                          # FastAPI entrypoint and HTTP-specific behavior
  mcp/                          # FastMCP server/client, schemas, tools and resources
  transport/http.py             # ASGI errors/observability shared by API and MCP
  cli/                          # explicit commands: ingestion, text, image, multimodal
```

## Dependency and placement rules

1. `domain` imports no other project layer. `application`, `retrieval` and
   `ingestion` may use core contracts but never import infrastructure, transport,
   CLI, composition, ORM, model/provider SDKs or web frameworks. Source-file and
   image adaptation remains in ingestion; outbound HTTP belongs to an adapter.
2. Put a port beside the use case that consumes it. Adapters implement that port
   and return domain/application values; ORM sessions and provider payloads must
   not become use-case inputs. Split modules when responsibilities diverge, not
   to create one class per file or speculative abstractions.
3. Infrastructure depends inward on core contracts. Keep ORM mappings in
   `persistence/models`, queries/writes in their adapters, and transaction
   coordination in `unit_of_work.py`. Share SQL filters through `search/filters.py`.
   Put model execution in `embeddings`, network providers in `providers`, and
   filesystem/decoding/download behavior in `media`.
4. Import complete metadata from `infrastructure.persistence.models` for Alembic
   or schema inspection. The registry imports all mapped tables and exports
   `Base`; individual models import `models.base`. Add every new table module to
   the registry. Model registration must never initialize engines, load models,
   call providers or import repositories.
5. `composition.py` builds shared capabilities; API/MCP/CLI entrypoints own
   process lifecycles and command-specific setup. Keep protocol parsing and
   responses in those entrypoints, reusable ASGI behavior in `transport`, and
   business decisions in use cases. MCP remains the protocol adapter, including
   its client; do not duplicate it under infrastructure.
6. Prefer explicit defining-module imports. Keep `__init__.py` lightweight;
   the ORM registry is the documented metadata-registration exception. Update
   call sites, tests, scripts and current documentation when moving modules.
   Historical evaluation reports keep their recorded commands. Avoid permanent
   compatibility re-exports for internal modules.

`make check` runs the package dependency contracts in
[tests/contract/test_package_boundaries.py](tests/contract/test_package_boundaries.py)
as part of the normal suite. These static checks cover ordinary absolute,
relative and function-local imports; dynamic import tricks are not a supported
way to cross a boundary. Existing integration tests verify migration/model
parity, repository atomicity, retrieval and both MCP transports.

## CLI path changes

Flags and behavior are retained. Use the following modules with
`uv run --locked python -m` from `backend/`; Makefile targets and current setup
instructions use these paths.

| Previous module | Current module |
| --- | --- |
| `food_recommender.ingestion.cli` | `food_recommender.cli.ingestion` |
| `food_recommender.retrieval.cli` | `food_recommender.cli.text` |
| `food_recommender.retrieval.image_cli` | `food_recommender.cli.image` |
| `food_recommender.retrieval.multimodal_cli` | `food_recommender.cli.multimodal` |

## Applying the structure in later phases

- **Phase 7:** keep graph state, node orchestration, prompts and control logic
  separate within `agents`. Inject inference and MCP capabilities through real
  boundaries; extend `providers/groq.py` or focused sibling modules for SDK calls.
  Keep deterministic dietary/citation rules in the core and saver setup in
  `persistence/checkpoints.py`.
- **Phase 8:** use focused API routers/schemas/dependencies over application use
  cases. Add catalog, session and conversation behavior to the relevant use-case
  modules and repository ports; preserve the shared unit of work for atomicity.
  Upload decoding/storage goes through the media adapters. HTTP/SSE code must not
  acquire SQLAlchemy sessions or instantiate providers directly.
- **Phase 9:** keep route shells and proxy code in frontend `app`, cohesive chat,
  preferences, recommendations and catalog behavior in `features`, genuinely
  shared UI in `components`, and generated contracts/clients in `lib`. Keep
  domain rules on the backend and use `PRODUCT_NAME` for product labels.
- **Phases 10–11:** check boundaries with acceptance tests and clean setup;
  verify new mappings register and match migrations, commands/import paths work,
  and import-time code performs no service connections or model loads. Record
  actual evidence before checking off the corresponding phase tasks.

## Phase 7 workflow boundaries

The implemented graph uses `agents/state.py` for JSON-only checkpoint channels,
`agents/nodes/` for the six role implementations, `agents/prompts.py` for versioned
instructions, `agents/graph.py` for routing and the explicit expert barrier, and
`agents/runner.py` for owned turns/cancellation. Reset/finalization are control
logic. `agents/telemetry.py` records allowlisted stage timing, without source text.

`application/inference.py` and `application/workflow.py` define the inference,
MCP gateway and owned-run lease ports. `application/profile_rules.py`,
`nutrition_rules.py` and `evidence_rules.py` keep correction, dietary and citation
rules independent of the graph/provider. `application/reliability.py` supplies
shared run budgets. Concrete Groq HTTP stays in `infrastructure/providers/groq.py`;
discovered tool schema/role enforcement stays in `mcp/client.py`; PostgreSQL lease
SQL and supported saver setup stay in `infrastructure/persistence/{runs,checkpoints}.py`.
The saver disables arbitrary class revival; graph state contains only JSON values.

`composition.build_workflow_roles` wires injected, scoped MCP role views and a
process-owned inference provider. Share the provider/semaphore and MCP client
across turns, with fresh application-issued run IDs. Optional synthetic review
context is supplied explicitly with a matching demo-profile scope. Graph imports
never load embeddings, open connections or contact providers. Boundary tests
cover the permitted LangGraph/LangChain dependencies and prevent concrete adapter
imports into nodes or core rules.
