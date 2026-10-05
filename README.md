# foodwise-ai

An English-language, local restaurant and recipe recommender based on the IBM
capstone. The planned application combines six LangGraph agents, cited text and
image retrieval, PostgreSQL/pgvector, OpenAI API (`gpt-4o-mini`), MCP, and live food trend search.

Phase 0 is verified, the P01-01 project layout is scaffolded, and P01-02 pins
the runtimes and backend/frontend dependency graphs. P01-03 adds validated
backend configuration; P01-04 adds safe examples, setup diagnostics and a
frontend public-environment guard. P01-05 adds a four-service local Compose
scaffold with persistent PostgreSQL/media storage and health checks. P01-06 adds
locked lint, formatting, type checking and Python/component/browser test tooling.
Locked installation and quality commands are documented in the
package READMEs; [Compose setup and verification](infra/README.md) are runnable.
P01-07 adds [GitHub Actions CI and local reproduction](infra/ci.md), including
real PostgreSQL/pgvector checks and offline provider/model fixtures.
P01-08 adds injectable services, typed errors and redacted JSON logging.
Start with the [developer workflow](infra/development.md) for locked setup,
local development, checks and command availability.
Phase 2 persistence, transactional repositories and conversation cleanup are
verified. Phase 3 ingestion/media and [Phase 4 text retrieval](evaluation/phase4/README.md)
and [Phase 5 multimodal retrieval/fusion](evaluation/phase5/README.md) are verified.
Phase 6 MCP/live trends and Phase 7 graph implementations are present.
The [OpenAI migration smoke](evaluation/openai-migration/README.md) returned five
validated recommendations; style/trend analysis was unavailable, so full live
acceptance remains open. [Phase 8](evaluation/phase8/README.md)
adds verified FastAPI conversations/SSE, private images, browsing, administrator
CRUD and generated TypeScript contracts. [Phase 9](evaluation/phase9/README.md)
adds the responsive meal workspace, preferences/uploads, cited category results,
catalog browsing and administrator CRUD. Production browser journeys verify
real API/database/MCP behavior with controlled inference; live acceptance remains
separate. Each P09 task has a dedicated commit on the frontend branch.

For this machine's memory constraints, see the [measured host assessment](infra/memory-assessment.md)
and [optional low-memory Compose setup](infra/README.md#running-with-limited-ram).

| Location | Purpose |
| --- | --- |
| [backend/](backend/README.md) | Python package boundaries, migrations, and backend tests. |
| [frontend/](frontend/README.md) | Next.js application and feature folders. |
| [evaluation/](evaluation/README.md) | Source evidence, labeled queries, fixtures, and measured reports. |
| [infra/](infra/README.md) | Container and local operational configuration. |
| `data/` | Original seed datasets and local recovered media. |
| `scripts/` | Existing Phase 0 audit and secret scan. |

See [AGENTS.md](AGENTS.md) for the architecture and
[CHECKLIST.md](CHECKLIST.md) for verified progress and remaining tasks.
The four course folders, assignment PDFs, recovered media, and real `.env`
files remain local and Git-ignored. Their recovery requirements are recorded in
the [Phase 0 report](evaluation/phase0/README.md).

Use [.env.example](.env.example) to fill missing local settings without replacing
an existing `.env`. The [backend configuration guide](backend/README.md#local-setup-and-offline-diagnostics)
documents an offline, redacted configuration check; the
[frontend guide](frontend/README.md) documents the browser-secret guard and tests.

OpenAI is the sole inference provider. Set `OPENAI_API_KEY` in the ignored root
`.env`; `OPENAI_MODEL` and `OPENAI_VISION_MODEL` independently default to
`gpt-4o-mini`. Embeddings remain local CPU models. After pulling this migration,
run `uv sync --locked` from `backend/` and rebuild any Compose backend/MCP images.
See the [migration evidence and limits](evaluation/openai-migration/README.md).
