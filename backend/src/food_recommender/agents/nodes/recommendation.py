"""Bounded synthesis; canonical constraints and citation grounding before publishing."""

from collections import Counter
from dataclasses import asdict, replace
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from food_recommender.agents.catalog_quotes import source_options
from food_recommender.agents.prompts import RECOMMENDATION
from food_recommender.agents.structured import (
    GroundingError,
    schema_feedback,
    structured,
)
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
    Recommendation,
    RecommendationResult,
    validate_recommendations,
)
from food_recommender.domain.values import EvidenceState, Strength
from food_recommender.retrieval.late_fusion import FusedCandidate


class RecommendationSelection(BaseModel):
    """Internal generation contract; public recommendations remain domain objects."""

    model_config = ConfigDict(extra="forbid", strict=True)
    recommendation_indices: tuple[Annotated[int, Field(ge=0)], ...] = Field(
        max_length=10
    )


SELECTION_ADAPTER = TypeAdapter(RecommendationSelection)


def quoted_recommendations(
    candidates: tuple[FusedCandidate, ...], style: ExpertOutcome[StyleAnalysis]
) -> tuple[Recommendation, ...]:
    by_entity = {c.evidence.entity: c for c in candidates}
    options = []
    assessments = style.result.assessments if isinstance(style, AgentSuccess) else ()
    for assessment in assessments:
        candidate = by_entity.get(assessment.entity)
        if candidate is None:
            continue
        for observation in assessment.observations:
            if publishable_catalog_span(observation) and supported_span(
                observation, candidate.evidence.citations, assessment.citation_ids
            ):
                options.append(
                    Recommendation(
                        assessment.entity, observation, assessment.citation_ids
                    )
                )
                break
    # Style may be unavailable or lack a grounded observation for some candidates.
    # Supply only validated catalog facts; synthesis still selects and is revalidated.
    covered = {option.entity for option in options}
    for candidate in candidates:
        if candidate.evidence.entity in covered:
            continue
        quotations = source_options(candidate)
        if quotations:
            quote = quotations[0]
            options.append(
                Recommendation(
                    candidate.evidence.entity, quote.observation, quote.citation_ids
                )
            )
    return tuple(options)


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
        grounded = quoted_recommendations(eligible, style)
        if not grounded:
            return AgentSuccess(
                RecommendationResult(
                    (),
                    (
                        *limitations,
                        "Insufficient eligible, publishable catalog evidence under unchanged constraints",
                    ),
                )
            )
        repair = None
        for attempt in range(2):
            try:
                selection = await structured(
                    self.inference,
                    RECOMMENDATION,
                    {
                        "profile": profile,
                        "eligible_candidates": eligible,
                        "grounded_recommendations": tuple(
                            {"recommendation_index": index, **asdict(option)}
                            for index, option in enumerate(grounded)
                        ),
                        "trend": trend,
                        "style": style,
                        "nutrition": nutrition,
                        "authoritative_nutrition": authoritative,
                        "repair": repair,
                    },
                    SELECTION_ADAPTER,
                    repairs=0,
                )
                indices = selection.recommendation_indices
                if len(set(indices)) != len(indices) or any(
                    index >= len(grounded) for index in indices
                ):
                    raise GroundingError(
                        "recommendation_indices must contain distinct indices from "
                        f"{list(range(len(grounded)))}. Copy the supplied "
                        "recommendation_index values; use [] if none qualify."
                    )
                selected = tuple(grounded[index] for index in indices)
                if any(
                    count > 5
                    for count in Counter(
                        item.entity.category for item in selected
                    ).values()
                ):
                    raise GroundingError(
                        "recommendation_indices selects more than five items in a "
                        "category. Select at most five per category."
                    )
                result = RecommendationResult(selected)
                evidence = tuple(c.evidence for c in eligible)
                try:
                    validate_recommendations(
                        result, evidence, nutrition=authoritative, hard_constraints=hard
                    )
                except ValueError:
                    raise GroundingError(
                        "recommendations contains an ineligible entity or unsupported "
                        "citation. Select only supplied recommendation_index values "
                        "from grounded_recommendations."
                    ) from None
                by_entity = {c.evidence.entity: c for c in eligible}
                items = []
                for index, item in enumerate(result.recommendations):
                    candidate = by_entity[item.entity]
                    if not publishable_catalog_span(
                        item.explanation
                    ) or not supported_span(
                        item.explanation,
                        candidate.evidence.citations,
                        item.citation_ids,
                    ):
                        raise GroundingError(
                            f"recommendations[{index}].explanation is not a publishable "
                            "verbatim excerpt supported by its citation_ids. Copy the "
                            "matching recommendation_index from grounded_recommendations; "
                            "do not generate explanation text or add facts."
                        )
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
            except ValidationError as error:
                repair = schema_feedback(error)
            except GroundingError as error:
                repair = str(error)
            except Exception:
                repair = "Previous output failed validation. Return recommendation_indices as an array of distinct supplied indices; at most five items per category. Do not generate recommendation objects or text."
        return AgentFailure("validation_failed")
