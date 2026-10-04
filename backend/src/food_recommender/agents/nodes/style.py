"""Bounded analysis of every canonical candidate; source-grounded observations."""

from pydantic import ConfigDict, TypeAdapter

from food_recommender.agents.prompts import STYLE
from food_recommender.agents.structured import structured
from food_recommender.application.evidence_rules import supported_span
from food_recommender.application.inference import Inference
from food_recommender.domain.experts import (
    AgentSuccess,
    AgentUnavailable,
    ExpertOutcome,
    ProfileResult,
    StyleAnalysis,
)
from food_recommender.domain.values import EvidenceState
from food_recommender.retrieval.late_fusion import FusedCandidate

type StyleContract = StyleAnalysis
STYLE_ADAPTER: TypeAdapter[StyleAnalysis] = TypeAdapter(
    StyleContract, config=ConfigDict(extra="forbid", strict=True)
)


class FoodStyleExpert:
    def __init__(self, inference: Inference, *, batch_size: int = 10) -> None:
        if not 1 <= batch_size <= 20:
            raise ValueError("Invalid expert batch size")
        self.inference, self.batch_size = inference, batch_size

    async def run(
        self, profile: ProfileResult, candidates: tuple[FusedCandidate, ...]
    ) -> ExpertOutcome[StyleAnalysis]:
        assessments = []
        try:
            for offset in range(0, len(candidates), self.batch_size):
                batch = candidates[offset : offset + self.batch_size]
                analysis = await structured(
                    self.inference,
                    STYLE,
                    {"profile": profile, "candidates": batch},
                    STYLE_ADAPTER,
                )
                by_entity = {c.evidence.entity: c for c in batch}
                if {a.entity for a in analysis.assessments} != set(by_entity):
                    raise ValueError("Analysis must cover all batch candidates")
                for item in analysis.assessments:
                    evidence = by_entity[item.entity].evidence
                    if not set(item.citation_ids) <= {c.id for c in evidence.citations}:
                        raise ValueError("Unsupported style citation")
                    if item.state == EvidenceState.CONFLICTING or any(
                        not supported_span(text, evidence.citations, item.citation_ids)
                        for text in item.observations
                    ):
                        raise ValueError("Unsupported style observation")
                    assessments.append(item)
            return AgentSuccess(StyleAnalysis(tuple(assessments)))
        except Exception:
            return AgentUnavailable("style_unavailable")
