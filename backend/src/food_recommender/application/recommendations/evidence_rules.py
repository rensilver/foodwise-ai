"""Deterministic grounding rules; generated prose cannot introduce source facts."""

import re

from food_recommender.domain.evidence import CandidateEvidence, Citation
from food_recommender.domain.values import EntityRef

CULINARY_TERMS = frozenset(
    {
        "italian",
        "mexican",
        "japanese",
        "indian",
        "korean",
        "mediterranean",
        "pizza",
        "pasta",
        "rice",
        "noodles",
        "sushi",
        "fermentation",
        "fermented",
        "sourdough",
        "barbecue",
        "seafood",
        "coffee",
        "tea",
        "desserts",
        "seasonal",
        "grains",
        "tomato",
        "basil",
    }
)


def terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.casefold())) & CULINARY_TERMS


def supported_span(
    text: str, citations: tuple[Citation, ...], identities: tuple[str, ...]
) -> bool:
    by_id = {c.id: c for c in citations}
    return bool(
        text.strip()
        and identities
        and len(set(identities)) == len(identities)
        and set(identities) <= by_id.keys()
        and any(
            text.casefold() in by_id[identity].excerpt.casefold()
            for identity in identities
        )
    )


def candidate_map(
    candidates: tuple[CandidateEvidence, ...],
) -> dict[EntityRef, CandidateEvidence]:
    result = {c.entity: c for c in candidates}
    if len(result) != len(candidates):
        raise ValueError("Duplicate candidate IDs")
    return result


def trend_signal(text: str) -> bool:
    words = set(re.findall(r"[a-z]+", text.casefold()))
    return bool(
        words
        & {
            "trend",
            "trends",
            "popular",
            "popularity",
            "growing",
            "growth",
            "surge",
            "demand",
            "viral",
            "seasonal",
        }
    ) and bool(
        words
        & (
            {"food", "foods", "cuisine", "dishes", "recipes", "restaurants", "cooking"}
            | (
                CULINARY_TERMS
                - {
                    "italian",
                    "mexican",
                    "japanese",
                    "indian",
                    "korean",
                    "mediterranean",
                }
            )
        )
    )
