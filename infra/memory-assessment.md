# Local memory assessment — 2026-10-02

The current Phase 1 scaffold runs on this host with the optional
[low-memory override](../compose.low-memory.yaml). The complete planned
recommender cannot yet be confirmed: ingestion, embeddings, retrieval and
six-agent orchestration remain future work. No model inference benchmark was
performed, and these limits are not a release or full-application acceptance
result.

## Hardware and pressure observed

| Item | Observation |
| --- | --- |
| CPU | AMD Ryzen 5 7520U, four cores / eight logical CPUs, x86_64. |
| OS-visible RAM | 6.538 GiB (6,855,248 KiB). |
| Swap | 4 GiB disk-backed `/swap.img`. |
| Initial pressure | About 871 MiB available RAM and only 1.7 MiB free swap. |
| Later baseline | About 3.5 GiB available RAM and 459 MiB free swap. |
| Workspace filesystem | Disk-backed NVMe; about 141 GiB free. |
| `/tmp` | 3.3 GiB tmpfs, about 2.2 GiB used. |
| Existing containers | Two unrelated `tasty-recipe-ai` containers, approximately 31 MiB combined in Docker stats. |
| IDE | VS Code processes summed to approximately 1.2 GiB resident memory; shared pages can be counted more than once. |

Snapshots are time-dependent. Mostly used swap alone does not establish
current swap thrashing: previously swapped pages can remain there after RAM
becomes available. The initial snapshot establishes little spare capacity at
that moment; no historical kernel OOM event was established by this audit.
Process names/RSS were inspected without printing command arguments or
credentials. Existing applications and host swap configuration were preserved.

## Verified scaffold runtime

`python infra/verify_compose.py --low-memory` passed using cached pinned
images, synthetic credentials, isolated volumes and random localhost ports.
All test resources were removed afterward. This measured one point after
startup and health requests, not peak usage or sustained recommendation load.

| Service | Measured cgroup memory | Enforced RAM ceiling |
| --- | --- | --- |
| PostgreSQL/pgvector | 94.6 MiB | 256 MiB |
| FastAPI | 68.6 MiB | 512 MiB |
| FastMCP | 155.2 MiB | 512 MiB |
| Next.js production server | 111.7 MiB | 384 MiB |
| Total | 430.1 MiB | 1,664 MiB |

Cgroup v2 accounting includes charged filesystem cache. Docker stats on Linux
can report smaller values after subtracting inactive file cache, so the two
measurements should not be treated as interchangeable. Container accounting
excludes the Docker daemon, desktop, IDE and build workers.

Verification covered all four healthy services, the frontend page, API
readiness, MCP initialization/discovery, vector cosine operations, actual
PostgreSQL memory settings, enforced container limits, limited database
privileges, read-only MCP media, data persistence after recreation and
redacted dependency failures. No tested container was OOM-killed or
automatically restarted. No OpenAI/Tavily calls or pretrained-model downloads
occurred.

`python infra/verify_compose.py --low-memory --build` also completed both
locked image builds sequentially, including the frontend's 1,024 MiB
old-space heap setting, and passed the complete smoke scenarios again with
the rebuilt images. Its post-startup container snapshot totaled 350.4 MiB.
A host snapshot during frontend compilation still
showed about 3.2 GiB available RAM. This is an observation during one build,
not a measured build-memory peak or a guarantee for a larger frontend.

## Configuration and remaining work

Use the commands in [the Compose guide](README.md#running-with-limited-ram).
The optional override uses one Python worker per service, bounded CPU-library
threads, a smaller PostgreSQL configuration and a capped production Node
heap. Equal RAM and combined RAM/swap limits disable container swap; they
bound memory use rather than reserve RAM. The default Compose configuration
remains available.

Build backend/frontend separately while leaving room for transient build
workers. The frontend override caps each build Node process's old-space heap
at 1,024 MiB; this is not a total Docker build memory limit. Avoid concurrent
browser suites, notebook kernels, local LLMs and image builds on this host.
If RAM becomes scarce, close unused IDE windows/browser tabs and stop
unneeded workloads deliberately. Do not disable swap or clear it while RAM
is under pressure.

Keep large model caches, media and scratch data on disk rather than this
host's RAM-backed `/tmp`. The ignored workspace `.local-tmp/` directory can
serve as a host-process `TMPDIR`; it is unrelated to Docker's internal build
filesystem. Existing `.env` settings and secrets were not read or changed.

MiniLM and CLIP dependencies are installed, but the current API/MCP paths
do not import/load their models. OpenAI executes language-model inference
remotely; six agent roles do not imply six resident local LLMs. For future
embedding work, use CPU inference, one resident owner per model, small
batches and bounded jobs; measure cold-load, ingestion and image-query peaks
before increasing or reusing the current memory ceilings. PyTorch libraries,
model weights and intermediate tensors can dominate memory even though the
small catalog's stored vectors are compact. A more comfortable hardware
target is 16 GB RAM, an engineering recommendation rather than a measured
minimum or a prerequisite for the current scaffold.

References: [Docker memory/swap limits](https://docs.docker.com/reference/compose-file/services/#memswap_limit),
[Docker stats cache accounting](https://docs.docker.com/reference/cli/docker/container/stats/),
[PostgreSQL resource settings](https://www.postgresql.org/docs/16/runtime-config-resource.html),
[Next.js memory guidance](https://nextjs.org/docs/app/guides/memory-usage).
