"""Bounded synthesis; canonical constraints and citation grounding before publishing."""

from dataclasses import replace

from pydantic import ConfigDict, TypeAdapter

from food_recommender.agents.prompts import RECOMMENDATION
from food_recommender.agents.structured import structured
from food_recommender.application.recommendations.evidence_rules import (
    publishable_catalog_span,
    supported_span,
)
from food_recommender.application.recommendations.inference import Inference
from food_recommender.application.recommendations.nutrition_rules import (
    deterministic_nutrition,
)
from food_recommender.application.recommendations.reliability import RunExhausted
from food_recommender.domain.experts import (
    AgentFailure,
    AgentSuccess,
    ExpertOutcome,
    NutritionAnalysis,
    ProfileResult,
    StyleAnalysis,
    TrendAnalysis,
)
from food_recommender.domain.recommendations import (
    RecommendationResult,
    validate_recommendations,
)
from food_recommender.domain.values import EvidenceState, Strength
from food_recommender.retrieval.late_fusion import FusedCandidate

type RecommendationContract = RecommendationResult
RESULT_ADAPTER: TypeAdapter[RecommendationResult] = TypeAdapter(
    RecommendationContract, config=ConfigDict(extra="forbid", strict=True)
)


class RecommendationExpert:
    def __init__(self, inference: Inference) -> None:
        self.inference = inference

    async def run(
        self,
        profile: ProfileResult,
        candidates: tuple[FusedCandidate, ...],
        trend: ExpertOutcome[TrendAnalysis],
        style: ExpertOutcome[StyleAnalysis],
        nutrition: ExpertOutcome[NutritionAnalysis],
    ) -> ExpertOutcome[RecommendationResult]:
        hard = any(c.strength == Strength.HARD for c in profile.preferences.constraints)
        authoritative = deterministic_nutrition(profile, candidates)
        states = {a.entity: a.state for a in authoritative.assessments}
        eligible = tuple(
            c
            for c in candidates
            if states[c.evidence.entity] != EvidenceState.CONFLICTING
            and (not hard or states[c.evidence.entity] == EvidenceState.SUPPORTED)
        )
        limitations = tuple(
            dict.fromkeys(
                (
                    *(
                        f"{label} analysis unavailable"
                        for label, outcome in (
                            ("Trend", trend),
                            ("Style", style),
                            ("Nutrition", nutrition),
                        )
                        if not isinstance(outcome, AgentSuccess)
                    ),
                    *(
                        gap
                        for c in candidates
                        for gap in c.evidence.limitations
                        if publishable_catalog_span(gap)
                    ),
                    "Synthetic course catalog; relevance is not dietary certification",
                    "No verified nutrient quantities or cross-contact safety evidence",
                )
            )
        )
        if not eligible:
            return AgentSuccess(
                RecommendationResult(
                    (),
                    (
                        *limitations,
                        "Insufficient eligible catalog evidence under unchanged constraints",
                    ),
                )
            )
        repair = None
        for attempt in range(2):
            try:
                result = await structured(
                    self.inference,
                    RECOMMENDATION,
                    {
                        "profile": profile,
                        "eligible_candidates": eligible,
                        "trend": trend,
                        "style": style,
                        "nutrition": nutrition,
                        "authoritative_nutrition": authoritative,
                        "repair": repair,
                    },
                    RESULT_ADAPTER,
                    repairs=0,
                )
                evidence = tuple(c.evidence for c in eligible)
                validate_recommendations(
                    result, evidence, nutrition=authoritative, hard_constraints=hard
                )
                by_entity = {c.evidence.entity: c for c in eligible}
                items = []
                for item in result.recommendations:
                    candidate = by_entity[item.entity]
                    if not publishable_catalog_span(
                        item.explanation
                    ) or not supported_span(
                        item.explanation,
                        candidate.evidence.citations,
                        item.citation_ids,
                    ):
                        raise ValueError("Unsupported explanation")
                    known = next(
                        a for a in authoritative.assessments if a.entity == item.entity
                    )
                    # Generated limitations cannot introduce medical claims or new facts.
                    items.append(
                        replace(
                            item,
                            limitations=(
                                *(
                                    gap
                                    for gap in candidate.evidence.limitations
                                    if publishable_catalog_span(gap)
                                ),
                                *known.limitations,
                            ),
                        )
                    )
                return AgentSuccess(RecommendationResult(tuple(items), limitations))
            except RunExhausted:
                return AgentFailure("budget_exhausted")
            except Exception:
                repair = "Previous output failed validation. Use only eligible IDs, their citation IDs and verbatim supported excerpts; at most five unique items per category."
        return AgentFailure("validation_failed")
