"""Deterministic culinary projections of immutable source records.

Offsets refer to this rendered projection, or directly to raw paragraph text.
Imported captions remain separate attributed documents, never ingredient facts.
"""

import hashlib
from collections.abc import Mapping

from food_recommender.domain.catalog import DocumentData

VERSION = "text-retrieval-v1"
FIELDS = {
    "restaurant": (
        "name",
        "description",
        "food_style",
        "location",
        "signature_dishes",
        "signatures",
        "vibe",
        "environment",
        "shortcomings",
    ),
    "recipe": ("name", "cuisine", "ingredients", "directions"),
    "review": ("title", "text", "review", "review_text"),
}


def render(
    category: str, payload: Mapping[str, object] | None, raw_text: str | None = None
) -> str:
    if category not in FIELDS:
        raise ValueError("Unsupported culinary source")
    if raw_text is not None:
        return raw_text
    lines = []
    for field in FIELDS[category]:
        value = (payload or {}).get(field)
        if isinstance(value, str) and value.strip():
            lines.append(f"{field}: {value}")
        elif (
            isinstance(value, list)
            and all(isinstance(item, str) for item in value)
            and value
        ):
            lines.append(f"{field}: " + "\n".join(value))
    return "\n".join(lines)


def document(
    record_id: str, category: str, text: str, *, start: int = 0, end: int | None = None
) -> DocumentData:
    end = len(text) if end is None else end
    excerpt = text[start:end]
    content_hash = hashlib.sha256(excerpt.encode()).hexdigest()
    identity = hashlib.sha256(
        f"{VERSION}:{record_id}:{start}:{end}:{content_hash}".encode()
    ).hexdigest()
    return DocumentData(
        id=identity,
        source_record_id=record_id,
        kind=f"retrieval_{category}",
        text=excerpt,
        start_offset=start,
        end_offset=end,
        content_hash=content_hash,
        ingestion_version=VERSION,
        attribution="source",
    )
