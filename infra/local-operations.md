# Local operation, troubleshooting and limits (P11-07)

This guide describes `foodwise-ai` as verified through 2026-10-06 in
America/Recife. Start a new installation with the
[clean-checkout setup](release-setup.md), which specifies pinned tools, fresh
private credentials, recovered media, CPU model provisioning, builds, migrations,
checkpoint setup, ingestion and indexing in order. Use the
[developer workflow](development.md) for host processes and checks, and the
[paired backup/restore procedure](backup-restore.md) before recovery that changes
stored data. Public hosting and multi-user accounts remain deferred.

## Providers and modes

| Requirement | Local behavior and verification boundary |
| --- | --- |
| OpenAI | Required for real profile extraction, expert analysis, synthesis and administrator extraction previews. `OPENAI_API_KEY` stays server-side; `OPENAI_MODEL` and `OPENAI_VISION_MODEL` default to `gpt-4o-mini`. Valid configuration and healthy services do not prove account access, quota or model capabilities. Use the separately opt-in [capability checks](../backend/README.md#phase-7-six-agent-workflow) or [live demo](live-demo.md); these issue billable calls. There is no automatic provider/model fallback. |
| Tavily | `TAVILY_API_KEY` enables fresh food-trend searches through MCP. A blank key permits startup and catalog use. Eligible cached evidence may still be used; otherwise trends are unavailable and recommendations can continue without trend claims. Dates and supported excerpts are required even when search succeeds. |
| Local embeddings | Pretrained, revision-pinned MiniLM and CLIP bundles are separate from locked package installation. Provision them before indexing; serving does not download weights. Text search and administrator embedding preparation use MiniLM; image retrieval needs CLIP and validated media associations. No OpenAI embedding service is used. |
| PostgreSQL, MCP and media | Catalog/history/checkpoints and retrieval need the initialized local database, shared media volume and reachable MCP. Offline unit fixtures do not supply these runtime dependencies. Base Compose keeps database/MCP private. |
| Optional Langfuse | Keep `LANGFUSE_ENABLED=false` and `LANGFUSE_CONVERSATION_EXPORT_VERIFIED=false` for normal operation. Cloud retention/deletion and Phase 11 Cloud operational gates remain open; the application works without tracing. See the [recorded tracing limits](../evaluation/phase10/README.md#p10-19--resource-limits-sampling-and-deletion). |

Catalog browsing does not invoke OpenAI or Tavily. An installed catalog remains
browsable during a provider outage while its local dependencies are available.
The isolated [administrator demo](admin-demo.md) and
[portfolio capture](portfolio-demo.md) use controlled inference with real local
retrieval; they document that mode and do not substitute for live-provider
acceptance. Missing style/trend analysis appears as a limitation. Profile,
retrieval or synthesis failures may end the turn with a typed error. Hard
dietary evidence gates remain active in every mode.

## Routine diagnostics

Run from the repository root, in the same shell as the `compose` helper from
[setup](release-setup.md#build-initialize-and-start-compose). That helper must
select the original project, dotenv and all override files on every command.
For a default installation it wraps `docker compose`; the isolated rehearsal
uses different images, volumes and dynamically assigned localhost ports.

```bash
compose config --quiet
compose ps
OPS_BACKEND_ADDRESS="$(compose port backend 8000)"
OPS_FRONTEND_ADDRESS="$(compose port frontend 3000)"
curl --fail --show-error "http://$OPS_BACKEND_ADDRESS/api/v1/health/live"
curl --fail --show-error "http://$OPS_BACKEND_ADDRESS/api/v1/health/ready"
curl --fail --show-error "http://$OPS_FRONTEND_ADDRESS/health/live"
curl --fail --show-error "http://$OPS_FRONTEND_ADDRESS/api/v1/recipes?limit=1"
compose logs --tail 100 backend mcp db frontend
```

Use `config --quiet`: resolved configuration can print secrets. Review logs
locally; application failures use redacted codes and request/run IDs, while
third-party/container output needs review before sharing. Do not share dotenv,
cookies, CSRF tokens, provider responses or private prompts/uploads.

For offline backend configuration syntax, run from `backend/`:

```bash
uv run --locked python -m food_recommender.infrastructure.config --env-file ../.env
```

Exit `0` means valid settings syntax; `2` means missing/invalid settings. This
does not connect to dependencies or check provider access. The host-process
database/MCP/media settings in the file differ from the internal addresses and
mounted paths supplied by Compose.

Liveness `200` means a process responds. Backend readiness `200` checks
database/pgvector, accessible media, reachable MCP, application/checkpoint
tables and the MiniLM manifest/files. It does not load the encoders, verify
every model file hash, require a populated catalog/index, check CLIP or issue
provider calls. Encoder loading validates bundle hashes separately. Catalog
probes, import/index reports and the live demonstration provide those additional
checks; a healthy empty catalog is possible.

## Troubleshooting

| Symptom | Check and recovery |
| --- | --- |
| Configuration exits `2`, or a container fails before serving | Follow the diagnostic's field names using [.env.example](../.env.example). Preserve existing settings; use absolute model/media paths, distinct URL-safe database passwords and a single-quoted Argon2id admin hash. Obtain fresh provider keys through the owner's account. Never print configuration to diagnose it. |
| Port is occupied or frontend proxy cannot reach the API | Check `compose ps` and the actual addresses from `compose port`. Use the isolated localhost-port override for a second stack. Host Next.js uses server-side `FOODWISE_API_ORIGIN`; host Python cannot reach unpublished base-Compose database/MCP ports. Follow [host development](development.md#host-development) for explicit host addresses. |
| Readiness `503`: `database` or `mcp` unavailable | Check the selected project's service health/logs and internal addresses. Recover the failed dependency, then probe again. A dotenv password edit does not rotate an existing database role. Preserve volumes and use deliberate credential maintenance or the paired restore procedure rather than reinitializing the owner's database. |
| Readiness `503`: `schema` unavailable | Complete `setup alembic upgrade head`, then `setup python scripts/setup_checkpoints.py` using the setup guide's helper and mounts. Ordinary startup does not migrate; production images omit migration/scripts/seed directories. Never downgrade a populated database as a startup repair. |
| Readiness `503`: `media` or `catalog_encoder` unavailable | Confirm the mounted media volume is writable by backend UID 10001 and readable by MCP. Confirm `MINILM_ROOT` is the provisioned absolute directory with its manifest/files and correct revision. Re-provision a damaged bundle into a new ignored directory, then update its selected mount. Do not bypass hashes or use random test models. |
| Empty catalog, absent image results or missing thumbnails despite readiness `200` | Check ingestion and both index summaries. Complete the setup sequence after models/media recovery. The full seed is 210 restaurants, 109 recipes and ten reviews (329 records), with 770 text and 118 image vectors when all imagery is available. Restore the nonempty recovered recipe ZIP and nine approved-host review files; keep rejects/missing-media issues visible. Recipe filenames identify actual IDs. Review imagery is scoped search evidence, not restaurant browse thumbnails. Repeated import/indexing is resumable and skips unchanged inputs. |
| Model identity/dimension/hash error | Use the pinned MiniLM 384-dimensional and CLIP 512-dimensional bundles from setup. Match each query to its modality/model revision. Correct provisioning and rerun the corresponding index command; do not relabel incompatible stored vectors or wipe indexes on startup. |
| Container OOM, stalled builds or slow first image query | Build backend/frontend sequentially and keep caches/scratch on disk. Inspect `docker stats --no-stream` and container exit status. The old 512 MiB MCP scaffold ceiling is below measured standalone CLIP peak RSS; use the setup guide's model-aware override consistently. Its ceilings are bounds, not a measured hardware minimum. Avoid concurrent indexing/build/browser workloads on the measured small host. |
| OpenAI unavailable, timeout/rate limit, invalid response or exhausted budget | Check configured account/model access and quota privately; inspect the redacted run failure. Calls have bounded retries/repairs. Wait for provider recovery and submit a new explicit request; do not assume restarting changes quota. Capability probes and live reruns incur provider usage. A rejected structured response is not published as an unvalidated fallback. |
| Trends unavailable or no dated claims | Check the MCP Tavily setting and the reported reason: missing credentials, timeout/rate limit, cache error, no results or stale evidence. Unknown publication dates cannot support current trends; a new retrieval timestamp does not refresh an old publication. Continue without trend claims or rerun explicitly when eligible evidence is available. Preserve this degradation label. |
| SSE disconnect, Stop, refresh or a concurrent-turn `409` | Refetch conversation history to see whether the response completed; completed responses are saved before the final payload. Never automatically replay the message POST. Disconnect/Stop cancels active work; refresh does not resume it. Wait for the active turn to finish/cancel before a new explicit turn. Prior restrictions survive follow-ups. |
| History or private upload returns `404` | Use the original browser session; ownership denial also returns `404`. Clearing cookies or using another browser does not transfer ownership. Check retained database/media volumes and, after recovery, the paired backup. Conversation deletion also removes its unshared uploads and checkpoint/profile context. |
| Administrator `401`, `403`, `409` or invalid input | Sign in again after expiry/logout (`401`); use the permitted origin and login-issued CSRF token (`403`). Review the latest version before explicitly resaving a preserved draft after a version conflict (`409`). Correct invalid fields (`422`). Confirm deletes in the UI. A cancelled dialog makes no write; browser disconnect does not undo an already committed write. See the [admin recovery evidence](../evaluation/phase11/README.md#p11-05--administrator-preview-searchable-crud-and-recovery). |
| No recommendations under an allergy/strict diet | Inspect cited ingredients/evidence and limitations. Conflicts and unknown compliance are withheld, and bounded refinements never relax a hard restriction. Ask about preferences or change a restriction only through an explicit user correction. Empty results can be the correct outcome; do not remove constraints to fill cards. |

Use `compose restart backend` for a process restart and `compose down` to stop
the selected stack while preserving named volumes. After settings/image changes,
recreate affected services using the same Compose selection. Do not use volume
deletion or global Docker pruning as troubleshooting. Restore only through the
[documented paired recovery](backup-restore.md); its evidence covers offline,
same-version recovery, without online/PITR/cross-version or Cloud guarantees.

## Catalog and unavailable capabilities

The synthetic course catalog is a small local demonstration dataset. Ten reviews
come from one synthetic user, so personalization uses content and explicit
conversation preferences, with session-scoped review evidence. There are no
social histories or collaborative-filtering claims. The importer retains 16
same-name/location review pairs for entity review; it preserves IDs rather than
silently merging them. Captions are attributed imported/generated text and do
not prove ingredients. See [source inventory](../evaluation/phase0/README.md)
and [ingestion evidence](../evaluation/phase3/README.md).

Nutrition quantities, comprehensive allergen absence and cross-contact safety
are unverified. Unknown dietary compliance stays unknown; hard restrictions
withhold unverifiable candidates. Catalog price bands/ratings belong to their
dataset source. Real-time menus, opening hours, delivery, reservation/ordering,
stock availability, coordinates and recipe difficulty have no verified source
here. Live trends supply dated culinary evidence, not new restaurant facts.
Scores measure relevance rather than confidence, rating or dietary certification.

Public hosting, multi-user accounts, social-media connectors, verified nutrition
and large-scale indexing are deferred. Local uploads/catalog CRUD are supported;
the app is not a public service or an unrestricted web/file-fetch tool. Recovered
media and course PDFs/notebooks remain separate, ignored recovery inputs; a
clean checkout alone does not contain them. Original-history publication review
and the complete-release/optional Cloud gates stay open in
[CHECKLIST.md](../CHECKLIST.md).

## Measured limits and enforced bounds

The Phase 10 measurements used Linux x86_64, an AMD Ryzen 5 7520U (eight logical
CPUs), about 6.538 GiB visible RAM and one CPU-library thread. Setup rehearsed
Python 3.12.14, uv 0.12.5, Node 24.19.0, pnpm 12.8.1, Next.js 16.3.8,
PostgreSQL 16.14/pgvector 0.8.6, Docker 29.8.0 and Compose 5.5.1. Refer to
the linked reports for revision, exact versions and measurement inputs; other
platforms and sustained concurrent-user capacity are unmeasured.

| Measurement | Recorded result | Scope |
| --- | --- | --- |
| CPU model load/peak RSS | MiniLM 8.534 s / 490.65 MiB; CLIP 6.886 s / 975.54 MiB | Separate fresh processes; uncontrolled OS cache, not combined service or build peaks. |
| Warm single-query encoding p95 | MiniLM 20.75 ms; CLIP 52.23 ms | Ten samples/model on the Phase 10 host. |
| Warm exact retrieval, default text/image 0.6/0.4 | Median 403.81 ms; p95 482.47 ms; Recall@20 1.000, nDCG@5 0.965, cuisine diversity@5 0.630 | 25 labeled queries, five settings, two executions; sparse relevance labels and catalog identity images, no OpenAI/Tavily. Empty labels excluded from recall/nDCG means. |
| Live restaurant / image recipe / allergy follow-up | 15.176 s / 8.555 s / 3.911 s; allergy turn returned no items | Three scripted P11-04 turns with real providers/retrieval/checkpoints; two positive turns have all six roles and dated trend evidence. |
| Usage for those live turns | 17 OpenAI attempts, 20,458 provider tokens, one fresh Tavily search | Excludes earlier failed rehearsals/diagnostics; no cost estimate or sustained-load claim. |
| Setup container ceilings | Backend 2,304 MiB; MCP 1,536 MiB; DB 256 MiB; frontend 384 MiB | P11-01 all healthy, zero OOM kills/restarts at inspection; ceilings are not observed peaks or memory reservations. |

Sources: [CPU performance report](../evaluation/phase10/performance_report.json),
[real retrieval report](../evaluation/phase10/retrieval_report.json),
[live-turn evidence](../evaluation/phase11/README.md#p11-04--live-text-image-six-agent-and-follow-up-demonstration)
and [setup report](../evaluation/phase11/clean_setup_report.json). The historical
[Phase 1 memory snapshot](memory-assessment.md) did not load pretrained models.
Fixture graph timing excludes real providers, network, database and browser and
must not be presented as live response latency. No minimum-RAM certification,
full-stack peak memory, concurrent-user throughput, representative live quality
or bill estimate has been measured.

Current enforced bounds are up to 20 candidates and five unique final items per
category, with an initial retrieval plus at most two refinements. A conversation
allows one active run. Defaults are a 120-second run deadline, 30-second call
budgets, three concurrent OpenAI calls/process, two transient retries, two shared
schema/domain repairs and one synthesis repair; waiting/retries share budgets.
These are application limits, not environment variables or latency promises.
Trend searches allow at most two fresh requests/run including retries and five
results/request; eligible evidence needs publication within 90 days and retrieval
within 24 hours. Uploads accept single-frame decoded JPEG/PNG/WebP, at most
10 MiB and 20 megapixels, and strip metadata. Sources:
[run bounds](../backend/src/food_recommender/application/recommendations/reliability.py),
[trend service](../backend/src/food_recommender/application/trends/service.py) and
[image validation](../backend/src/food_recommender/infrastructure/media/images.py).

P11-07 publishes these operational instructions and recorded limits. It does
not close complete-release acceptance (P11-08), final user review (P11-09),
clean-checkout path rehearsal (P11-10) or optional Cloud tasks (P11-11/12).
