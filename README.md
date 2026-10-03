# foodwise-ai

An English-language, local restaurant and recipe recommender based on the IBM
capstone. The planned application combines six LangGraph agents, cited text and
image retrieval, PostgreSQL/pgvector, Groq, MCP, and live food trend search.

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
Agent reasoning and recommendation interfaces remain planned.

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
