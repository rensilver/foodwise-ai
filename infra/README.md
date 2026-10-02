# Infrastructure scaffold

This directory reserves service container definitions and local operational
configuration. The root [.dockerignore](../.dockerignore) provides initial
repository-context exclusions for credentials, course references, recovered
media, and development caches. Future Dockerfiles must also use explicit copy
paths; service-specific build contexts need equivalent exclusions.

P01-05 will add the root `compose.yaml` and PostgreSQL/pgvector, backend,
FastMCP, and Next.js services with pinned images, mounted storage, and health
checks. Published ports must bind to `127.0.0.1`, with database and MCP access
internal by default. Compose startup and container build commands are pending.
