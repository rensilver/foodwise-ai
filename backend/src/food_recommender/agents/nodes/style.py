"""Bounded style selection over source quotations for every canonical candidate."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from food_recommender.agents.prompts import STYLE
from food_recommender.agents.structured import structured
from food_recommender.application.recommendations.evidence_rules import (
    instruction_span,
    publishable_catalog_span,
    supported_span,
)
from food_recommender.application.recommendations.inference import Inference
from food_recommender.domain.experts import (
    AgentSuccess,
    AgentUnavailable,
    ExpertOutcome,
    ProfileResult,
    StyleAnalysis,
    StyleAssessment,
)
from food_recommender.domain.values import EvidenceState
from food_recommender.retrieval.late_fusion import FusedCandidate


class StyleOption(BaseModel):
    observation: str
    citation_ids: tuple[str, ...]


class StyleSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_index: int = Field(ge=0, le=19)
    option_index: Annotated[int, Field(ge=0, le=11)] | None = None


class StyleSelections(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: tuple[StyleSelection, ...] = Field(max_length=20)


def source_options(candidate: FusedCandidate) -> tuple[StyleOption, ...]:
    options = []
    for citation in candidate.evidence.citations:
        if instruction_span(citation.excerpt):
            continue
        lines = citation.excerpt.splitlines()
        observations = [
            line
            for line in lines
            if line.startswith(
                ("cuisine:", "food_style:", "signatures:", "directions:")
            )
        ]
        if not observations:
            observations = [citation.excerpt[:2000]]
        for observation in observations:
            if publishable_catalog_span(observation) and supported_span(
                observation, (citation,), (citation.id,)
            ):
                options.append(
                    StyleOption(observation=observation, citation_ids=(citation.id,))
                )
    return tuple(options[:12])


class FoodStyleExpert:
    def __init__(self, inference: Inference, *, batch_size: int = 10) -> None:
        if not 1 <= batch_size <= 20:
            raise ValueError("Invalid expert batch size")
        self.inference, self.batch_size = inference, batch_size

    async def run(
        self, profile: ProfileResult, candidates: tuple[FusedCandidate, ...]
    ) -> ExpertOutcome[StyleAnalysis]:
        assessments: list[StyleAssessment] = []
        try:
            for offset in range(0, len(candidates), self.batch_size):
                batch = candidates[offset : offset + self.batch_size]
                options = tuple(source_options(candidate) for candidate in batch)

                def validate(result: StyleSelections) -> None:
                    indices = [
                        selection.candidate_index for selection in result.selections
                    ]
                    if len(indices) != len(batch) or set(indices) != set(
                        range(len(batch))
                    ):
                        raise ValueError(
                            "Analysis must cover every batch candidate exactly once"
                        )
                    for selection in result.selections:
                        if (
                            selection.option_index is not None
                            and selection.option_index
                            >= len(options[selection.candidate_index])
                        ):
                            raise ValueError("Unknown source option")

                result = await structured(
                    self.inference,
                    STYLE,
                    {
                        "profile": profile,
                        "candidates": batch,
                        "grounded_options": options,
                    },
                    TypeAdapter(StyleSelections),
                    validate=validate,
                )
                for selection in sorted(
                    result.selections, key=lambda item: item.candidate_index
                ):
                    candidate = batch[selection.candidate_index]
                    option = (
                        options[selection.candidate_index][selection.option_index]
                        if selection.option_index is not None
                        else None
                    )
                    if option is not None and (
                        not publishable_catalog_span(option.observation)
                        or not supported_span(
                            option.observation,
                            candidate.evidence.citations,
                            option.citation_ids,
                        )
                    ):
                        raise ValueError("Unsupported style observation")
                    assessments.append(
                        StyleAssessment(
                            candidate.evidence.entity,
                            EvidenceState.SUPPORTED
                            if option
                            else EvidenceState.UNKNOWN,
                            option.citation_ids if option else (),
                            (option.observation,) if option else (),
                            ()
                            if option
                            else ("No supported style observation selected",),
                        )
                    )
            return AgentSuccess(StyleAnalysis(tuple(assessments)))
        except Exception:
            return AgentUnavailable("style_unavailable")
