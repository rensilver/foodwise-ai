"""Structured nutrition analysis with authoritative deterministic exclusions."""

from dataclasses import replace

from pydantic import ConfigDict, TypeAdapter

from food_recommender.agents.prompts import NUTRITION
from food_recommender.agents.structured import structured
from food_recommender.application.inference import Inference
from food_recommender.application.nutrition_rules import deterministic_nutrition
from food_recommender.domain.experts import (
    AgentSuccess,
    ExpertOutcome,
    NutritionAnalysis,
    NutritionAssessment,
    ProfileResult,
)
from food_recommender.retrieval.late_fusion import FusedCandidate

type NutritionContract = NutritionAnalysis
NUTRITION_ADAPTER: TypeAdapter[NutritionAnalysis] = TypeAdapter(
    NutritionContract, config=ConfigDict(extra="forbid", strict=True)
)


class NutritionExpert:
    def __init__(self, inference: Inference, *, batch_size: int = 10) -> None:
        if not 1 <= batch_size <= 20:
            raise ValueError("Invalid expert batch size")
        self.inference, self.batch_size = inference, batch_size

    async def run(
        self, profile: ProfileResult, candidates: tuple[FusedCandidate, ...]
    ) -> ExpertOutcome[NutritionAnalysis]:
        authoritative = deterministic_nutrition(profile, candidates)
        result: list[NutritionAssessment] = []
        for offset in range(0, len(candidates), self.batch_size):
            batch = candidates[offset : offset + self.batch_size]
            checks = authoritative.assessments[offset : offset + self.batch_size]
            try:
                analysis = await structured(
                    self.inference,
                    NUTRITION,
                    {
                        "profile": profile,
                        "candidates": batch,
                        "deterministic_assessments": checks,
                    },
                    NUTRITION_ADAPTER,
                )
                by_entity = {a.entity: a for a in checks}
                if {a.entity for a in analysis.assessments} != set(by_entity):
                    raise ValueError("Missing nutrition assessments")
                for item in analysis.assessments:
                    known = by_entity[item.entity]
                    if item.state != known.state or not set(item.citation_ids) <= set(
                        known.citation_ids
                    ):
                        raise ValueError("Inference cannot override canonical evidence")
                # Preserve verified limitations; do not publish generated medical prose.
                result.extend(checks)
            except Exception:
                result.extend(
                    replace(
                        item,
                        limitations=(
                            *item.limitations,
                            "Structured nutrition analysis unavailable",
                        ),
                    )
                    for item in checks
                )
        return AgentSuccess(NutritionAnalysis(tuple(result)))
