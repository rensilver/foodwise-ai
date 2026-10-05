"""Canonical ingredients control compliance; inferred analysis cannot upgrade it."""

from food_recommender.domain.experts import (
    NutritionAnalysis,
    NutritionAssessment,
    ProfileResult,
)
from food_recommender.domain.values import EvidenceState, Strength
from food_recommender.retrieval.dietary import assess
from food_recommender.retrieval.late_fusion import FusedCandidate


def deterministic_nutrition(
    profile: ProfileResult, candidates: tuple[FusedCandidate, ...]
) -> NutritionAnalysis:
    assessments = []
    for candidate in candidates:
        checks = tuple(
            assess(c, candidate.ingredients, candidate.allergens)
            for c in profile.preferences.constraints
            if c.strength == Strength.HARD
        )
        states = {check.state for check in checks}
        state = (
            EvidenceState.CONFLICTING
            if EvidenceState.CONFLICTING in states
            else EvidenceState.UNKNOWN
            if not checks or EvidenceState.UNKNOWN in states
            else EvidenceState.SUPPORTED
        )
        assessments.append(
            NutritionAssessment(
                candidate.evidence.entity,
                state,
                tuple(c.id for c in candidate.evidence.citations),
                tuple(
                    dict.fromkeys(
                        (
                            *[c.reason for c in checks],
                            "No verified nutrient quantities or cross-contact safety evidence",
                        )
                    )
                ),
            )
        )
    return NutritionAnalysis(tuple(assessments))
