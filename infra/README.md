# Local Compose scaffold

[compose.yaml](../compose.yaml) starts four local services. This is a working
startup scaffold: culinary tools, migrations, ingestion, recommendations, the
API proxy and the full user interface remain their later checklist tasks.

| Service | Runtime and health check | Host access |
| --- | --- | --- |
| `db` | PostgreSQL 16.14 and pgvector, pinned by image digest; readiness requires PostgreSQL and the vector extension. | Internal `db:5432` only. |
| `mcp` | Shared Python 3.12.14 image; FastMCP Streamable HTTP at `/mcp`; `/health/ready` checks PostgreSQL/pgvector and readable media. | Internal `mcp:8001` only. |
| `backend` | FastAPI; `/api/v1/health/ready` checks PostgreSQL/pgvector, writable media and MCP readiness. | `127.0.0.1:8000`. |
| `frontend` | Next.js standalone production server on Node 24.19.0; `/health/live` checks HTTP serving. | `127.0.0.1:3000`. |

Python, Node and uv base images have exact version tags and immutable digests.
The backend image uses uv 0.12.5 and `uv sync --locked --no-dev --no-editable`;
the frontend uses pnpm 12.8.1 and `pnpm install --frozen-lockfile`. Both runtime
images run as non-root users. Repository-context
[exclusions](../.dockerignore) and explicit Dockerfile copy paths keep dotenv
files, course material, data, media and development caches out of the images.
Builds download dependencies; they do not fetch pretrained models or call
Groq/Tavily. The first backend build includes the locked CPU embedding libraries
and can take several minutes.

The verification target is Linux x86_64 with Docker 29.8.0 and Compose 5.5.1.
The database digest pins that upstream platform artifact; other architectures
have not been tested. This host rejects container process execution with
`no-new-privileges` enabled, so the Compose scaffold omits that optional setting.

From the repository root, use Docker Engine and Compose v2.24.4 or newer:

```bash
docker compose version
docker compose config --quiet
docker compose build backend frontend
docker compose up -d --wait --wait-timeout 180
docker compose ps
curl --fail http://127.0.0.1:8000/api/v1/health/ready
curl --fail http://127.0.0.1:3000/health/live
```

Before those commands, fill missing entries in your existing root `.env` using
[.env.example](../.env.example). If no `.env` exists, copy the example first.
Supply a fresh `GROQ_API_KEY`, a single-quoted Argon2id `ADMIN_PASSWORD_HASH`,
and distinct `POSTGRES_PASSWORD` and `FOODWISE_DB_PASSWORD` values. Generate
each database password independently with `openssl rand -hex 32`, then save
the values locally. `FOODWISE_DB_PASSWORD` permits letters, digits, `_` and `-`
because Compose embeds it in a URL; initialization rejects other characters.
Leave Tavily blank to keep trends unavailable. Missing required entries stop
Compose with a setting name and corrective instruction. Avoid plain
`docker compose config` in shared logs: resolved output includes credentials.

Compose explicitly selects each service's environment. It overrides host-run
`DATABASE_URL`, `MCP_SERVER_URL` and `MEDIA_ROOT` with internal service addresses
and `/var/lib/foodwise/media`. The frontend receives no backend configuration;
MCP receives only the database URL and media root. No root dotenv file is
copied or mounted into containers. Configuration validation checks syntax;
startup and health checks do not verify paid provider access.

The `postgres_data` volume persists PostgreSQL, and `media_data` persists media.
Backend media is writable by UID 10001; MCP mounts the same volume read-only.
The database initialization script runs only on a fresh database volume: it
enables pgvector and creates the `foodwise` login with schema privileges but
without superuser, database/role creation or replication privileges. Services
use that login; `postgres` is reserved for initialization/maintenance. Phase 2
will add application migrations; the scaffold creates no catalog tables.

Changing password variables does not rotate credentials in an existing
PostgreSQL volume. If initialization was interrupted or credentials changed,
inspect the database logs and repair that volume deliberately; do not delete
an existing database to resolve configuration errors. The default stack has
no database/MCP host ports. Host-run adapters need separately provisioned
services or an explicit local-only port override.

```bash
docker compose logs --tail 100 backend mcp db frontend
docker compose restart backend
docker compose down
```

`down` stops containers and preserves the named volumes. Health dependency
conditions gate startup using
[Compose's documented readiness behavior](https://docs.docker.com/compose/how-tos/startup-order/).
Liveness stays independent of dependencies; backend/MCP readiness returns a
redacted `503` when local dependencies are unavailable. Healthy means the
scaffold can serve requests, not that recommendations or live trends exist.
The frontend check reports its HTTP availability, while backend readiness
reports backend dependencies. Reserved ports must be free on your machine.

Run the isolated verification from the repository root:

```bash
python infra/verify_compose.py --build
```

[The smoke test](verify_compose.py) creates synthetic settings, a unique Compose
project and random localhost ports. It checks all four services, MCP
initialization/empty discovery, application-role privileges, the read-only
media mount, database/media persistence across container recreation, and
redacted readiness failures during MCP/database outages. It removes only its
own containers, volumes and ignored temporary configuration, including on
failure. It never loads the owner's `.env` or uses paid providers. Omit
`--build` to reuse already built scaffold images. Run it with a host Python
3.12+ interpreter and Docker access; Snap Docker needs permission to access
this repository.

The MCP scaffold follows
[FastMCP HTTP deployment](https://gofastmcp.com/deployment/http) and exposes no
placeholder culinary tools/resources. Its HTTP transport restricts hosts and
origins. FastAPI restricts hosts and enables no cross-origin browser access.
The frontend follows
[Next.js standalone output](https://nextjs.org/docs/app/api-reference/config/next-config-js/output);
full UI/proxy security checks are still required when those features arrive.

The pinned FastMCP client/server currently returns `Method not found` for
protocol ping during this smoke test. Compose uses the custom HTTP readiness
route. Initialization and tool/resource discovery are checked separately;
complete transport compatibility, including ping, remains Phase 6 work.
