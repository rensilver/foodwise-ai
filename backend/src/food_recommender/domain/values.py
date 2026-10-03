"""Shared immutable value types; no framework, provider or persistence imports."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class Category(StrEnum):
    RESTAURANT = "restaurant"
    RECIPE = "recipe"


class Origin(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class Strength(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class ConstraintKind(StrEnum):
    ALLERGEN = "allergen"
    DIETARY = "dietary"


class EvidenceState(StrEnum):
    SUPPORTED = "supported"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


class AgentRole(StrEnum):
    USER_PROFILE_GENERATOR = "user_profile_generator"
    RAG_RETRIEVER = "rag_retriever"
    FOOD_TREND_ANALYST = "food_trend_analyst"
    FOOD_STYLE_EXPERT = "food_style_expert"
    NUTRITION_EXPERT = "nutrition_expert"
    RECOMMENDATION_EXPERT = "recommendation_expert"


def nonempty(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty text")


def unique[T](values: tuple[T, ...]) -> None:
    if not isinstance(values, tuple) or len(set(values)) != len(values):
        raise ValueError("Expected an immutable tuple of unique values")


def unit_score(value: float) -> None:
    if isinstance(value, bool) or not isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Expected a finite relevance score between zero and one")


@dataclass(frozen=True)
class EntityRef:
    category: Category
    id: str

    def __post_init__(self) -> None:
        nonempty(self.id)
