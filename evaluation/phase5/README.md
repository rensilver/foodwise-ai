# Phase 5 — Multimodal retrieval and fusion

Verified locally on 2026-10-03 against a separate seeded PostgreSQL database,
pinned pretrained CPU MiniLM/CLIP and the recovered course media. Each of the
eight Phase 5 tasks has a separate branch commit. Agent reasoning, MCP tools,
live trends, upload HTTP endpoints and browser journeys remain later phases.

[21 frozen queries](queries.json) reuse all 17 Phase 4 text labels and add four
recipe/mixed-modality cases. [The measured report](comparison_report.json)
contains all five weight settings, per-category ranks, raw/normalized scores,
citations, effective weights, degradation, first/warm latency, source/model
hashes, hardware and software versions. Labels were fixed before these
experiments; unlabeled results receive zero gain.

| Setting (text/image) | Recall@20 | nDCG@5 | Cuisine diversity@5 | Warm median | Warm p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Text only (1.0/0.0) | 1.000 | 0.921 | 0.613 | 45.37 ms | 122.76 ms |
| Balanced (0.5/0.5) | 1.000 | 0.960 | 0.603 | 392.35 ms | 462.54 ms |
| Text heavy (0.8/0.2) | 1.000 | 0.928 | 0.592 | 401.12 ms | 667.37 ms |
| Image heavy (0.2/0.8) | 0.974 | 0.980 | 0.634 | 392.64 ms | 473.68 ms |
| Initial default (0.6/0.4) | 1.000 | 0.960 | 0.582 | 395.86 ms | 474.10 ms |

The initial 0.6/0.4 default remains unchanged. On these sparse labels, images
improve early precision at additional CPU cost. Image-heavy fusion loses one
of M21's two positives: the pizza image pushes the text-relevant tomato soup
outside the top 20. Its higher aggregate nDCG therefore does not establish a
better general default. Diversity measures distinct known cuisines divided by
the returned top-five count; it does not measure nutritional variety. Timing
uses two executions per query/setting on a shared host and is descriptive,
without statistical significance claims. Text-only skips CLIP encoding/search;
other settings include query encoding, ownership/hash checks for paired images,
exact DB retrieval and fusion. Model loading is excluded from query latency.

The corpus has 210 restaurants, 109 recipes, ten synthetic reviews, 770 text
vectors and 118 image vectors. All 109 recipe filename identities and original
image hashes match the validated Phase 0 media manifest. Nine review images
link through their actual reviews; profile-scoped review retrieval is required.
There is no general restaurant image corpus. Recipe images never provide
restaurant menu evidence, including when entity ID strings coincide.

Three real image-only queries (pizza, tomato soup, ramen) return the originating
recipe first. Three CLIP text-to-image queries return their source-backed recipe
first too. These are narrow fixtures. Paired query images are exact catalog
images; their matching performance does not establish generalization to user
photos, novel dishes or dietary compliance.

Every evaluated result has zero fabricated entity/citation IDs, hard-constraint,
metadata-filter, review-scope or image-association violations and zero duplicate
entities. Both successful and empty restrictive cases are checked. No OpenAI,
Tavily or other paid-provider calls were made. Model loading took 7.66 seconds;
peak process RSS was 1130.71 MiB, on an AMD Ryzen 5 7520U with 8 logical CPUs
and about 6.54 GiB RAM, with one CPU inference thread. PostgreSQL was 16.14,
pgvector extension 0.8.6, Torch 2.14.1+cpu and Transformers 5.18.0.

## Behavior and limits

Lexical/dense text evidence uses equal-weight entity RRF (`k=60`). Late fusion
normalizes text RRF and maximum image cosine scores separately within each
category. Each entity contributes its maximum per modality. Missing individual
evidence contributes zero; equal nonempty scores normalize to one. Unavailable
or empty whole modalities renormalize active weights and expose limitations.
Stable entity IDs break ties. Original scores, canonical ingredients, media IDs
and source-backed association citations remain available for inspection.

The shared service rechecks hard constraints before fusion. Known conflicts and
unknown strict compliance are excluded regardless of image similarity. Source
captions and visual similarity do not certify ingredients, allergen absence or
cross-contact safety. Empty searches and dependency failures are distinct;
requests using unauthorized/malformed query media abort with a typed failure.
Image decoding supports static JPEG/PNG/WebP, at most 10 MiB/20 megapixels.
Application query images use authorized media IDs, never paths or arbitrary URLs.

The synthetic catalog, sparse labels, same-corpus query images, limited review
history and partial restaurant imagery restrict the conclusions. No full
recommendation, live-trend or public-release quality claim follows from this
retrieval benchmark. Original publication/history and entity-review blockers
remain in [the checklist](../../CHECKLIST.md).

## Reproduce

Follow [backend setup](../../backend/README.md) and the
[disposable database guide](../../infra/ci.md). Use a separate evaluation DB,
apply migrations and run seed ingestion with the restored recipe ZIP and cached
review images. Set `DATABASE_URL`, `MEDIA_ROOT`, `MINILM_ROOT` and `CLIP_ROOT`
to that DB and ignored local storage, then run from `backend/`:

```bash
make provision-minilm
make provision-clip
make index-text
make index-images
make evaluate-multimodal
```

Model provisioning is an explicit public download, never startup/test behavior.
CLIP pins `openai/clip-vit-base-patch32` revision
`3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268` and verifies a complete local hash
manifest. The [model card](https://huggingface.co/openai/clip-vit-base-patch32)
and [Transformers CLIP reference](https://huggingface.co/docs/transformers/model_doc/clip)
describe the shared text/image model; outputs are normalized before storage or
search. Models stay local on CPU and queries reject incompatible revisions,
dimensions, nonfinite vectors and oversized CLIP text rather than truncating it.

Rerunning image indexing here reports 118 unchanged, zero embedded. Normal
CI uses deterministic fake boundaries/seeded fixtures without pretrained
network downloads. Optional `TEST_MINILM_ROOT` and `TEST_CLIP_ROOT` contracts
load separately provisioned pretrained models offline; configured broken models
fail. The full local backend `make check` passed: 355 tests without skips, Ruff,
formatting and mypy, with both pretrained flags and real PostgreSQL. Document
links/fences, task IDs, the AGENTS.md size budget and a redacting source scan
also passed.
