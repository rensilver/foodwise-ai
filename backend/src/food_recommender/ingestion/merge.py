"""Identity joins with explicit authoritative-field conflict detection."""

from dataclasses import dataclass
from typing import Any

from food_recommender.ingestion.adapters import SourceError


@dataclass(frozen=True)
class MergedRecord:
    payload: dict[str, Any]
    sources: tuple[tuple[str, dict[str, Any]], ...]


def indexed(
    records: list[dict[str, Any]], identity: str, source: str
) -> dict[int, dict[str, Any]]:
    result = {}
    for record in records:
        key = record.get(identity)
        if type(key) is not int or key <= 0:
            raise SourceError(source, "?", "Missing or invalid identity")
        if key in result:
            raise SourceError(source, key, "Duplicate identity")
        result[key] = record
    return result


def merge_records(
    base: list[dict[str, Any]],
    augmented: list[dict[str, Any]],
    *,
    identity: str,
    enrichment: set[str],
    base_source: str,
    augmented_source: str,
) -> tuple[MergedRecord, ...]:
    originals = indexed(base, identity, base_source)
    additions = indexed(augmented, identity, augmented_source)
    for key, record in additions.items():
        if key not in originals:
            raise SourceError(augmented_source, key, "Enrichment has no base record")
        for field, value in record.items():
            if field not in enrichment and (
                field not in originals[key] or originals[key][field] != value
            ):
                raise SourceError(
                    augmented_source, key, f"Authoritative field conflict: {field}"
                )
    result = []
    for key, original in originals.items():
        extra = additions.get(key)
        payload = dict(original)
        sources = [(base_source, dict(original))]
        if extra is not None:
            payload.update(
                {field: value for field, value in extra.items() if field in enrichment}
            )
            sources.append((augmented_source, dict(extra)))
        result.append(MergedRecord(payload, tuple(sources)))
    return tuple(result)
