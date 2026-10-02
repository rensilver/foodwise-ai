# Foodwise AI

An English-language, local restaurant and recipe recommender based on the IBM
capstone. The planned application combines six LangGraph agents, cited text and
image retrieval, PostgreSQL/pgvector, Groq, MCP, and live food trend search.

Phase 0 is verified, the P01-01 project layout is scaffolded, and P01-02 pins
the runtimes and backend/frontend dependency graphs. Locked installation
commands are documented in the package READMEs. Application startup and quality
commands will be added as their Phase 1 tasks are completed.

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
