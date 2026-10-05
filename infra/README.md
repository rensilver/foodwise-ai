# Local Compose operations

Start a new installation with the [clean-checkout setup guide](release-setup.md).
It includes fresh credential configuration, separately recovered media, pinned
model downloads, sequential image builds, migrations, supported checkpoints,
seed ingestion and indexing before all-service startup. [P11-01 evidence](../evaluation/phase11/README.md)
records the isolated rehearsal and its limits. For host development and quality
commands, see the [developer workflow](development.md).
For repeatable migration, ingestion, readiness and restart acceptance, use the
[P11-02 verifier](release-setup.md#migration-ingestion-and-restart-verification-p11-02).

[compose.yaml](../compose.yaml) runs four local services:

| Service | Runtime and readiness | Host access |
| --- | --- | --- |
| `db` | Digest-pinned PostgreSQL 16.14/pgvector; extension and server health. | Internal `db:5432` only. |
| `mcp` | FastMCP culinary retrieval/trend tools and resources; database/readable media readiness. | Internal `mcp:8001` only. |
| `backend` | FastAPI recommendations/SSE, catalog, private images and local administration; readiness also requires MCP, schema/checkpoints and a provisioned MiniLM bundle. | `127.0.0.1:8000`. |
| `frontend` | Next.js standalone meal workspace and same-origin API proxy; HTTP liveness. | `127.0.0.1:3000`. |

Python, Node and uv base images have exact version tags and immutable digests.
Backend builds use uv 0.12.5 and the locked production dependency graph;
frontend builds use pnpm 12.8.1 and the frozen lockfile. Both runtime images run
as non-root users. [Build exclusions](../.dockerignore) keep secrets, local
models/media and course artifacts out of images. Builds do not call providers
or download pretrained models. The tested platform is Linux x86_64, Docker
29.8.0 and Compose 5.5.1; other architectures are unverified.

Compose selects service-specific environments. Internal database/MCP/media
addresses replace host-process values from the root dotenv file. The frontend
receives only its API origin, plus any explicit runtime heap setting. Backend
provider/admin secrets stay server-side; MCP receives its database, media,
models and Tavily settings. Root dotenv files are never mounted. Use
`docker compose config --quiet`; ordinary resolved configuration prints secrets.

The named `postgres_data` and `media_data` volumes persist local data. Media is
writable by backend UID 10001 and mounted read-only by MCP. Pinned model bundles
are host bind mounts, read-only in serving containers. Database bootstrap runs
only on a fresh volume and creates the limited `foodwise` login; application
migrations and LangGraph checkpoint initialization are explicit setup steps.
Changing dotenv passwords does not rotate an existing volume's credentials.
Never delete an owner's volume to repair startup.

After completing initialization, use these commands from the root, with the
same Compose files/project and credentials selected during setup:

```bash
docker compose up -d --no-build --wait --wait-timeout 180
docker compose ps
curl --fail http://127.0.0.1:8000/api/v1/health/ready
curl --fail http://127.0.0.1:3000/health/live
docker compose logs --tail 100 backend mcp db frontend
docker compose restart backend
docker compose down
```

`down` preserves named volumes. Database and MCP have no published host ports;
use one-off setup containers on the private network, or a deliberately selected
localhost-only override for host development. Dependency health gates service
startup. Liveness stays independent of dependencies; readiness reports redacted
`503` failures. Health does not verify inference credentials, populated indexes
or dated live trends; those require their separately recorded checks.

[The Phase 1 verifier](verify_compose.py) records the earlier scaffold's isolated
health/persistence/outage contracts. Its empty-tool discovery and environment
assertions describe that historical scaffold and are not the current application's
release rehearsal. Use the clean-checkout sequence above for P11-01.

## Running with limited RAM

[compose.low-memory.yaml](../compose.low-memory.yaml) is an optional override
originally measured for the Phase 1 scaffold. Its MCP ceiling is below the
standalone CLIP peak measured in Phase 10; use the current setup guide's
model-aware override for the rehearsal. Use the same override files on every
Compose command; dropping them removes their limits when containers are recreated.

| Service | RAM ceiling | Adjustment |
| --- | --- | --- |
| PostgreSQL | 256 MiB | 64 MB shared buffers, 2 MB query work memory, 32 MB maintenance memory, 16 MB autovacuum memory, 20 connections, no parallel query workers. |
| FastAPI | 512 MiB | One Uvicorn worker; one thread per configured OpenMP/BLAS library. |
| FastMCP | 512 MiB | Same Python settings. |
| Next.js | 384 MiB | Production server with a 256 MiB V8 old-space heap ceiling. |

The combined container RAM ceilings are 1,664 MiB (1.625 GiB), excluding
Docker, the desktop, IDE and image builds. These are maximum limits, not
reservations or predictions of consumption. The override sets
`memswap_limit` equal to `mem_limit`, so these containers cannot consume host
swap; exhausted limits can cause an OOM kill. Automatic failure restarts are
bounded to three attempts. See [Docker's memory limit semantics](https://docs.docker.com/reference/compose-file/services/#memswap_limit).
This protects against unbounded container growth but cannot prevent unrelated
host applications or builds from exhausting system RAM.

With the existing local `.env` completed, run from the repository root:

```bash
docker compose -f compose.yaml -f compose.low-memory.yaml config --quiet
docker compose -f compose.yaml -f compose.low-memory.yaml up -d --no-build --wait --wait-timeout 180
docker compose -f compose.yaml -f compose.low-memory.yaml ps
docker stats --no-stream
```

If images need building, first make room in RAM and build each image
separately, before starting the stack:

```bash
docker compose -f compose.yaml -f compose.low-memory.yaml build backend
docker compose -f compose.yaml -f compose.low-memory.yaml build frontend
```

The frontend override supplies `FOODWISE_BUILD_NODE_OPTIONS` to its Dockerfile
to cap each build Node process's old-space heap at 1,024 MiB. The production
container's smaller `NODE_OPTIONS` is separate. A Node heap limit does not cap
total process memory or the sum of build workers; service limits do not apply
to Docker builds. Sequential builds reduce competition for RAM. Prefer the
production server over running an additional Next.js development server.

The historical low-memory smoke checked
resolved and enforced limits, actual PostgreSQL settings, cgroup v2 memory
usage, and absence of OOM kills/automatic restarts, as well as the existing
health, discovery, persistence and outage contracts. It uses cgroup v2
accounting on the verified Linux host; other cgroup layouts are unverified.

The [host assessment](memory-assessment.md) records measured hardware and
verification limits. The original scaffold measurements did not load pretrained embedding models.
Phase 10 measured standalone CPU model peaks; the 512 MiB MCP ceiling is
insufficient evidence for resident CLIP inference. Measure full-service model
loading and inference peaks before reusing these ceilings. Plan one owner for each resident model,
CPU inference, small batches and bounded embedding jobs. OpenAI's six agent
roles use remote inference; they do not require six local LLM instances.

This host's `/tmp` is a 3.3 GiB tmpfs, so large temporary files consume
RAM/swap. Keep model caches, media and installation/build scratch files on
the disk-backed workspace or another disk directory. For host-run tools,
create a workspace `.local-tmp/` directory and pass its absolute path as
`TMPDIR` only to commands that need it; keep that directory Git-ignored.
The default Compose media volume already uses disk-backed Docker storage.
Increasing disk-backed swap may provide emergency headroom, but swap is
slower than RAM and does not replace reducing the active workload.
