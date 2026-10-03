"""Bounded parsing of course image references without executing source data."""

import ast

from food_recommender.ingestion.adapters import SourceError


def parse_images(value: object, source: str, record_id: object) -> tuple[str, ...]:
    def reject() -> SourceError:
        return SourceError(
            source,
            record_id,
            "Invalid image list (max 16 KiB, 20 distinct string references, 2048 characters each)",
        )

    if value is None:
        return ()
    if isinstance(value, str):
        if len(value.encode()) > 16384:
            raise reject()
        try:
            tree = ast.parse(value, mode="eval")
            if sum(1 for _ in ast.walk(tree)) > 100:
                raise reject()
            value = ast.literal_eval(tree)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            raise reject() from None
    if not isinstance(value, list) or len(value) > 20:
        raise reject()
    if any(
        not isinstance(item, str) or not item.strip() or len(item) > 2048
        for item in value
    ):
        raise reject()
    if len(set(value)) != len(value):
        raise reject()
    return tuple(value)
