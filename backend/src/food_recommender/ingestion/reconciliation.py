"""Reviewable hash-bound paragraph mappings; never renumber legacy entities."""

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from food_recommender.ingestion.adapters import SourceError


@dataclass(frozen=True)
class ParagraphMapping:
    paragraph: int
    content_hash: str
    text: str
    status: Literal["mapped", "unresolved", "accepted_addition"]
    entity_id: str | None
    accepted_fields: dict[str, Any] | None = None


def stable_addition_id(content_hash: str) -> str:
    return str(
        uuid5(NAMESPACE_URL, f"foodwise-ai:course-restaurants:addition:{content_hash}")
    )


def read_paragraphs(content: str) -> list[str]:
    chunks = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    if not chunks or "Culinary" not in chunks[0]:
        raise SourceError(
            "California-Culinary-Map.txt", "heading", "Missing culinary-map heading"
        )
    return chunks[1:]


def reconcile(
    paragraphs: list[str],
    rows: list[dict[str, Any]],
    existing_ids: set[str],
    accepted: dict[str, dict[str, Any]] | None = None,
) -> tuple[ParagraphMapping, ...]:
    source = "restaurant paragraph mapping"
    accepted = accepted or {}
    if len(rows) != len(paragraphs):
        raise SourceError(source, "?", "Mapping must account for every paragraph")
    mapped = {row.get("paragraph"): row for row in rows}
    if set(mapped) != set(range(1, len(paragraphs) + 1)):
        raise SourceError(source, "?", "Duplicate or invalid paragraph numbers")
    seen = set()
    used_acceptances = set()
    result = []
    for number, text in enumerate(paragraphs, 1):
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        row = mapped[number]
        if row.get("source_sha256") != content_hash:
            raise SourceError(source, number, "Paragraph hash mismatch; review mapping")
        entity_id = row.get("itemId")
        fields = None
        if entity_id is not None:
            entity_id = str(entity_id)
            if entity_id not in existing_ids or entity_id in seen:
                raise SourceError(source, number, "Unknown or duplicate restaurant ID")
            seen.add(entity_id)
            status: Literal["mapped", "unresolved", "accepted_addition"] = "mapped"
        elif content_hash in accepted:
            fields = dict(accepted[content_hash])
            entity_id = stable_addition_id(content_hash)
            used_acceptances.add(content_hash)
            status = "accepted_addition"
        else:
            status = "unresolved"
        result.append(
            ParagraphMapping(number, content_hash, text, status, entity_id, fields)
        )
    if seen != existing_ids or used_acceptances != set(accepted):
        raise SourceError(
            source, "?", "Unmapped existing IDs or stale accepted additions"
        )
    return tuple(result)
