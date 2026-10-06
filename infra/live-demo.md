# Live recommendation demonstration (P11-04)

Run from the repository root with the locked backend environment. This deliberate
opt-in uses paid OpenAI inference and Tavily search. Use fresh owner-issued keys
in the original private dotenv; the verifier does not copy that file or its
keys into a rehearsal file. Langfuse export is disabled.

Prerequisites: Docker, installed locked backend dependencies, the revision-pinned
MiniLM/CLIP bundles, the recovered `data/synthetic-recipe-images.zip`, and the
nine approved-host review download cache files. Complete the
[local setup](release-setup.md) first. Ordinary CI never runs this live command.

```bash
backend/.venv/bin/python infra/verify_live_demo.py \
  --enable-live \
  --env-file .env \
  --minilm-root .local-tmp/minilm \
  --clip-root .local-tmp/clip \
  --review-cache .local-tmp/ingestion/downloads \
  --output evaluation/phase11/live_demo_report.json
```

The verifier creates a separate, automatically named PostgreSQL/pgvector
container with a random localhost port and generated database credentials.
It applies migrations and supported checkpoint initialization, imports the
complete synthetic course catalog into an empty database, and builds the 770
MiniLM and 118 CLIP vectors through normal adapters. Review downloads and model
files are reused locally; the recipe archive is validated again. The owner's
running services, configuration and catalog are preserved. Database/MCP secrets
are not placed in command arguments or the report.

The live probe then performs three scripted turns in one owned UUID conversation:

1. Ask for a Korean restaurant in Fullerton, with explicit cuisine/location.
2. Upload the catalog's Beef Bulgogi image through the normal bounded media
   service and ask for a Korean recipe using its application-issued media ID.
   Recipe retrieval does not apply the retained restaurant location.
3. Introduce an explicit hard soy allergy in the retained conversation. The
   catalog lacks verified allergen compliance, so retrieval and synthesis must
   withhold recommendations without erasing the cuisine preference.

Each positive turn must have all six roles succeed, cited catalog recommendations,
real dense text scores, and actual dated web trend claims. The image turn also
requires CLIP image scores, an actual `search_images` call, and recovery of the
image's own recipe identity. Timing spans prove sequential profile/retrieval,
overlapping trend/style/nutrition execution, and one synthesis after their join.
Candidate IDs and citation IDs are checked against that turn's retrieved set.
Trend analysis selects eligible, contiguous source spans by index. Style analysis
selects a source option or an unknown assessment for every candidate in each
bounded batch. The application revalidates and copies the original quotations;
synthesis receives rechecked style quotations as optional source-grounded guidance. Schema and grounding repairs
share the same bounded repair allowance and run deadline. Inferred profile additions
must name the restriction in a verbatim current-message quote; hard additions also
require restriction language. Placeholder restrictions are rejected, and omitted
fields preserve prior restrictions.
Web citations must have HTTPS URLs, provider-supplied publication dates within
90 days, and retrieval timestamps. Tavily receives explicit start/end dates and
publication filtering; the application independently checks freshness. Tavily
dates can reflect source updates, so the report does not independently certify
editorial publication metadata. A successful search alone does not satisfy the trend-claim gate.
Any degraded positive turn fails the verifier and stops further live turns.

The upper bound is three runs of 120 seconds each, 30-second calls, three
concurrent OpenAI calls, two transient retries, bounded schema/synthesis repairs,
and at most two Tavily searches per run (six across the script). Fresh eligible
cache hits can reduce live search usage. These are limits, not expected charges;
the report records actual tokens/searches and latency. A rerun incurs new provider
usage and overwrites the specified report, so preserve a prior report if needed.

The report contains only scripted demo preferences, synthetic catalog evidence,
public web excerpts/citations, opaque generated IDs and operational measurements.
It contains no owner history, keys, raw provider responses, or local storage paths.
Inspect the `passed`, per-turn `checks`, `synthetic_context_removed`, and `isolation`
fields before accepting a run. On failure, private redacted stage logs remain
under ignored `.local-tmp/p11-04-*`; failure does not authorize checking the task.
The verifier removes its container/anonymous database volume, generated media,
review cache copy, conversation/checkpoints and synthetic upload.

This demonstration verifies live integration for a deliberately small query set,
not representative relevance, verified nutrition, allergy safety, restaurant
availability, browser screenshots or administrator CRUD. Synthetic catalog and
source/entity-review/publication limitations remain. P11-05 onward and the full
release gate require their own evidence. See the
[recorded results](../evaluation/phase11/README.md#p11-04--live-text-image-six-agent-and-follow-up-demonstration).
