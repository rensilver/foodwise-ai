# foodwise-ai

An English-language, local restaurant and recipe recommender based on the IBM
capstone. The planned application combines six LangGraph agents, cited text and
image retrieval, PostgreSQL/pgvector, Groq, MCP, and live food trend search.

Phase 0 is verified, the P01-01 project layout is scaffolded, and P01-02 pins
the runtimes and backend/frontend dependency graphs. P01-03 adds validated
backend configuration; P01-04 adds safe examples, setup diagnostics and a
frontend public-environment guard. Locked installation and configuration test commands
are documented in the package READMEs. Application startup and quality
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

Use [.env.example](.env.example) to fill missing local settings without replacing
an existing `.env`. The [backend configuration guide](backend/README.md#local-setup-and-offline-diagnostics)
documents an offline, redacted configuration check; the
[frontend guide](frontend/README.md) documents the browser-secret guard and tests.
