"""Per-record durable progress; database checkpoints are the authority on resume."""

import asyncio
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.ingestion.adapters import INGESTION_VERSION, SourceError
from food_recommender.ingestion.extraction import atomic_json
from food_recommender.ingestion.models import IngestionStore, SeedItem


class ImportRunner:
    def __init__(self, store: IngestionStore, manifest: Path) -> None:
        self.store = store
        self.manifest = manifest

    async def run(
        self,
        items: list[SeedItem],
        *,
        issues: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "ingestion_version": INGESTION_VERSION,
            "status": "running",
            "metadata": metadata or {},
            "items": [
                {
                    "category": item.category,
                    "id": item.data.id,
                    "fingerprint": item.fingerprint,
                    "status": "pending",
                    "media": [asdict(media) for media in item.media],
                }
                for item in items
            ],
            "issues": issues or [],
        }

        async def save() -> None:
            counts = Counter(row["status"] for row in report["items"])
            counts.update(issue["status"] for issue in report["issues"])
            report["totals"] = {
                key: counts[key]
                for key in (
                    "imported",
                    "unchanged",
                    "rejected",
                    "unresolved",
                    "pending",
                )
            }
            await asyncio.to_thread(atomic_json, self.manifest, report)

        await save()
        try:
            for item, row in zip(items, report["items"], strict=True):
                try:
                    row["status"] = await self.store.upsert(item)
                except SourceError as error:
                    row.update(status="rejected", reason=error.reason)
                except ApplicationError as error:
                    if error.code not in {
                        ErrorCode.INVALID_REQUEST,
                        ErrorCode.CONFLICT,
                    }:
                        raise
                    row.update(status="rejected", reason=error.code.value)
                await save()
        except BaseException:
            report["status"] = "interrupted"
            await save()
            raise
        report["status"] = "completed"
        await save()
        return report
