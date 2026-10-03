"""Synthesis invariants against the retrieved evidence set."""

from dataclasses import dataclass

from food_recommender.domain.evidence import CandidateEvidence
from food_recommender.domain.experts import NutritionAnalysis
from food_recommender.domain.values import (
    Category,
    EntityRef,
    EvidenceState,
    nonempty,
    unique,
)


@dataclass(frozen=True)
class Recommendation:
    entity: EntityRef
    explanation: str
    citation_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        nonempty(self.explanation)
        unique(self.citation_ids)
        if not self.citation_ids:
            raise ValueError("Recommendations require citations")
        for identity in self.citation_ids:
            nonempty(identity)


@dataclass(frozen=True)
class RecommendationResult:
    recommendations: tuple[Recommendation, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        unique(tuple(item.entity for item in self.recommendations))
        for category in Category:
            if (
                sum(item.entity.category == category for item in self.recommendations)
                > 5
            ):
                raise ValueError(
                    "At most five recommendations per category are permitted"
                )


def validate_recommendations(
    result: RecommendationResult,
    candidates: tuple[CandidateEvidence, ...],
    *,
    nutrition: NutritionAnalysis | None = None,
    hard_constraints: bool = False,
) -> None:
    """Fail closed for missing restriction assessments; do not infer compliance.

    Ingredient checks produce the authoritative assessment in later retrieval
    work. This function only validates references and enforces that assessment.
    """
    unique(tuple(candidate.entity for candidate in candidates))
    by_entity = {candidate.entity: candidate for candidate in candidates}
    assessments = (
        {item.entity: item for item in nutrition.assessments} if nutrition else {}
    )
    for item in result.recommendations:
        candidate = by_entity.get(item.entity)
        if candidate is None:
            raise ValueError("Recommendation references an unknown candidate")
        allowed = {citation.id for citation in candidate.citations}
        if not set(item.citation_ids) <= allowed:
            raise ValueError("Recommendation references an unsupported citation")
        assessment = assessments.get(item.entity)
        if assessment is not None:
            if not set(assessment.citation_ids) <= allowed:
                raise ValueError(
                    "Restriction assessment references an unsupported citation"
                )
            if assessment.state == EvidenceState.CONFLICTING:
                raise ValueError("Recommendation conflicts with a restriction")
        if hard_constraints and (
            assessment is None or assessment.state != EvidenceState.SUPPORTED
        ):
            raise ValueError("Recommendation lacks supported restriction compliance")
