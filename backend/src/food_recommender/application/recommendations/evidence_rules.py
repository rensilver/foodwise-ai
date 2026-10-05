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


# The demo has no verified medical measurements, operating data or catalog trends.
# A quote alone cannot certify these claims, even when it is verbatim source text.
_UNSUPPORTED_CLAIMS = re.compile(
    r"\b(?:guaranteed?|(?:allergen|peanut|milk|dairy|egg|soy|wheat|sesame|nut)[ -]free|allergy[ -]safe)\b"
    r"|\bsafe\b.{0,40}\b(?:allerg|peanut|milk|cross[ -]contact)"
    r"|\b(?:no|zero|without)\b.{0,25}\bcross[ -](?:contact|contamination)\b"
    r"|\b\d+(?:\.\d+)?\s*(?:kcal|calories|grams?\s+of\s+(?:protein|fat|carbohydrates?|sugar|sodium)|(?:g|mg)\s+(?:protein|fat|carbohydrates?|sugar|sodium))\b"
    r"|\b(?:protein|fat|carbohydrates?|sugar|sodium)\s*[:=]\s*\d+(?:\.\d+)?\s*(?:g|mg)\b"
    r"|\$\s*\d+(?:\.\d+)?|\bverified\s+(?:rating|reviews?)\b"
    r"|\b(?:open\s+(?:until|from|at|daily)|opening\s+hours)\b"
    r"|\b(?:delivery|reservations?|menu items?)\b.{0,30}\bavailable\b"
    r"|\b(?:currently\s+(?:popular|viral)|trending|viral)\b",
    re.IGNORECASE,
)


def publishable_catalog_span(text: str) -> bool:
    """Conservative demo claim gate; this is not a general natural-language verifier."""
    return not bool(_UNSUPPORTED_CLAIMS.search(text)) and not instruction_span(text)


_INSTRUCTION_SPAN = re.compile(
    r"\bignore\b.{0,30}\b(?:instructions?|prompts?|rules?)\b"
    r"|\b(?:reveal|expose|print|send|read)\b.{0,50}\b(?:secret|api[ _-]?key|password|system[ _-]?prompt)\b"
    r"|\b(?:call|execute|run|invoke)\b.{0,50}\b(?:delete[_ -]catalog|shell|sql|new[_ -]tool)\b"
    r"|<\s*/?\s*(?:system|developer)\b",
    re.IGNORECASE,
)


def instruction_span(text: str) -> bool:
    """Reject recognizable injected instructions in published source spans."""
    return bool(_INSTRUCTION_SPAN.search(text))
