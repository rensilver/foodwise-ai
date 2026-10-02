# Phase 0 baseline evidence — 2026-10-02

Run `python scripts/phase0_audit.py` and `python scripts/scan_secrets.py` from the repository root to regenerate/check these results. The audit needs Pillow and reads no environment file or provider key.

## Source transfer and credentials

- The 12 assignment PDFs and four copied course folders remain local and Git-ignored, as requested. The 12 notebooks and two scripts from `ibm-rag-agentic-ai/11_capstone_project` are sanitized reference copies here. Two workflow notebook cells that assigned `GROQ_API_KEY` were replaced with an environment setup comment; the original repository was not edited. Stored notebook outputs were scanned for common credential patterns. A clean checkout needs these optional reference files supplied separately.
- [source_manifest.json](source_manifest.json) records the 35 original artifact slots, roles, sizes and SHA-256 hashes of available nonsecret copies. The old `03_agents/.env` is intentionally excluded and has no hash. The original zero-byte ZIP was replaced locally by an owner-recovered, validated archive.
- The owner confirmed on 2026-10-02 that the exposed Groq key was revoked and replaced. The new local `.env` remains ignored; no key was printed, tested, copied, or committed. `.env.example` contains names and safe placeholders only.
- The redacting source scanner found zero token/private-key patterns in 29 text source files. The current Git history contains one initial commit and no tracked environment file. The original repository still tracks `11_capstone_project/03_agents/.env` and the credential-bearing workflow notebook in commit `c5845e8`; publication or history cleanup there is a separate owner decision. No history was rewritten.

## Source validation and reconciliation

- [source_validation.json](source_validation.json): 204 unique restaurant IDs, 109 unique recipe IDs, ten unique review IDs from one synthetic user, nine review image URLs with nine matching captions, and zero orphan review links. Three restaurant vibes are null. Base and augmented recipe/review ID sets match.
- [restaurant_reconciliation.json](restaurant_reconciliation.json) maps 204 of 210 raw paragraphs to existing `itemId` values, with source excerpts and paragraph hashes. Six have no structured record: paragraph 26 **Surfside Grill**, 58 **Kimchi Kingdom**, 93 **The Copper Whisk**, 109 **The Iron Lotus**, 185 **The Copper Pot** in Sacramento, and 205 **The Salty Pelican**. Keep them unresolved until Phase 3 extraction/review assigns stable IDs.
- Sixteen pairs share normalized restaurant name and location. Several have conflicting price bands or ratings. The report lists their IDs and values; no records were merged or deleted. A human entity decision is required before canonical ingestion.

## Recovered media

- [recipe_media_manifest.json](recipe_media_manifest.json) records the 109 recovered `recipe{id}.png` files, SHA-256, dimensions and numeric recipe link. All 109 decoded as PNG, all recipe IDs 1–109 are covered, and there are no missing, extra, duplicate-ID, or duplicate-content files. The images total 215,942,257 bytes and remain local/ignored by Git; a clean checkout needs the recovered media separately.
- The owner-supplied nonempty ZIP is 215,139,852 bytes. All 109 image members passed bounded count/size/expansion, path, regular-file, CRC and byte-for-byte hash checks against the extracted PNGs. The archive was inspected without extraction. Its download URL was not independently verified. The original course ZIP was zero bytes; the replacement ZIP is local and Git-ignored.
- The nine review image URLs are references, not locally recovered files. `review_image_placeholder.jpeg` has no proven entity association and cannot fill recipe or review gaps.

## Follow-up source work

The six unmatched paragraphs and 16 possible duplicate pairs are reported for Phase 3 entity review rather than silently ingested. Keep the original repository's tracked credential/history exposure out of publication until separately addressed. Restore Git-ignored reference files and media from approved local sources on a clean checkout. Phase 1 scaffolding may proceed with these limitations visible.
