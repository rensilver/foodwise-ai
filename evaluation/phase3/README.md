# Phase 3 ingestion acceptance — 2026-10-03

[Seed report](seed_report.json) records the real PostgreSQL import, all paragraph
mappings, source hashes, media hashes/associations, unresolved groups and verified
versions. The catalog contains **210 restaurants, 109 recipes and 10 reviews**,
up from the original **204/109/10**. All original IDs and review links remain.

[Accepted additions](accepted_restaurant_additions.json) contains six manually
reviewed records keyed by the exact raw paragraph SHA-256. Only facts explicitly
present in paragraphs 26, 58, 93, 109, 185 and 205 were copied; unavailable fields
stay null. IDs are deterministic UUIDs derived from those paragraph hashes.
[The correction ledger](restaurant_corrections.json) changes `1000003`'s unsupported
legacy price band 5 to band 4 because paragraph 3 explicitly says `$$$$`.
The original JSON is unchanged; PostgreSQL retains both raw value and correction
provenance. The importer rejects stale or unsupported corrections.

The import persisted 329 entities, 18 source revisions and 777 source records.
All 109 recovered recipe images and nine approved-host review downloads were
decoded, stripped of metadata and stored under generated private names.
The 118 media rows and 118 imported captions have actual entity/media links.
A separate audit decoded and hash-checked every stored image (235,244,472 bytes)
and verified zero orphan review links or unlinked source records/captions.
No placeholder imagery, generated replacement corpus or paid inference was used.

The second full import used cached review images: **329 unchanged, 0 imported,
0 rejected, 0 pending**. All catalog versions stayed at 1. **16 unresolved
same-name/location groups** appear individually in the report and the CLI's
unresolved total; their source IDs are retained pending entity review. All 210
raw paragraphs have a mapped or reviewed accepted restaurant. These identity
groups are reported limitations, not silently merged entities.

Final verification passed all **284 backend tests without skips**, including
real PostgreSQL/pgvector, migrations and offline pre-provisioned CPU model
contracts. Ruff lint/format and strict mypy passed. Provider tests used fake
boundaries; provider text/vision access was not smoke-tested during this phase. Embedding tables remain
empty because generation and retrieval belong to Phases 4–5.

To reproduce, follow [backend ingestion instructions](../../backend/README.md#seed-ingestion-phase-3)
after restoring the separately ignored ZIP and migrating an explicitly selected
local database. The CLI defaults to both committed review ledgers. Unchanged
reruns do not download images unless the cache is missing and download is enabled.
Reports, cache and private media default to ignored `.local-tmp/ingestion/`.
On this workstation the accepted catalog is in the dedicated `foodwise_seed`
database of `foodwise-phase3-postgres`, with PostgreSQL data retained in
`foodwise_phase3_postgres_data`. Use `docker port foodwise-phase3-postgres 5432`
to inspect its localhost port; it is independent of existing application containers
and Compose volumes. Media and database storage remain local, separately restored
on clean checkouts. The original-repository credential-history publication review
is still pending, and public hosting remains deferred.
