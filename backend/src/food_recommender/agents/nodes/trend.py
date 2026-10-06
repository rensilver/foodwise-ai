"""Dated, relevant public MCP evidence; no private query context crosses the wire."""

import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from food_recommender.agents.prompts import TREND
from food_recommender.agents.structured import structured
from food_recommender.application.recommendations.evidence_rules import (
    instruction_span,
    supported_span,
    terms,
    trend_signal,
)
from food_recommender.application.recommendations.inference import Inference
from food_recommender.application.recommendations.workflow import ToolGateway
from food_recommender.application.trends.service import (
    Concept,
    TrendResult,
    trend_citations,
)
from food_recommender.domain.evidence import Citation
from food_recommender.domain.experts import (
    AgentSuccess,
    AgentUnavailable,
    ExpertOutcome,
    ProfileResult,
    TrendAnalysis,
    TrendClaim,
)
from food_recommender.domain.values import EntityRef
from food_recommender.retrieval.late_fusion import FusedCandidate


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str = Field(min_length=1, max_length=2000)
    entities: tuple[EntityRef, ...] = Field(min_length=1, max_length=40)
    citation_ids: tuple[str, ...] = Field(min_length=1, max_length=5)


class TrendDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: tuple[ClaimDraft, ...] = Field(default=(), max_length=5)


class TrendSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    option_indices: tuple[Annotated[int, Field(ge=0, le=4)], ...] = Field(
        default=(), max_length=5
    )


def grounded_options(
    candidates: tuple[FusedCandidate, ...], citations: tuple[Citation, ...]
) -> tuple[ClaimDraft, ...]:
    """Offer contiguous source spans that already satisfy the unchanged claim gate."""
    options = []
    for citation in citations:
        text = citation.excerpt
        breaks = list(re.finditer(r"\n\s*\n", text))
        starts = [0, *(match.end() for match in breaks)]
        ends = [*(match.start() for match in breaks), len(text)]
        eligible = []
        for index, start in enumerate(starts):
            for end in ends[index : index + 3]:
                quote = text[start:end].strip()
                entities = tuple(
                    c.evidence.entity
                    for c in candidates
                    if terms(quote)
                    & terms(" ".join(item.excerpt for item in c.evidence.citations))
                )
                if entities and trend_signal(quote) and not instruction_span(quote):
                    eligible.append(
                        ClaimDraft(
                            claim=quote, entities=entities, citation_ids=(citation.id,)
                        )
                    )
        if eligible:
            options.append(min(eligible, key=lambda option: len(option.claim)))
    return tuple(options)


class FoodTrendAnalyst:
    def __init__(
        self,
        inference: Inference,
        tools: ToolGateway,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.inference, self.tools, self.clock = inference, tools, clock

    async def run(
        self, profile: ProfileResult, candidates: tuple[FusedCandidate, ...]
    ) -> ExpertOutcome[TrendAnalysis]:
        if not candidates:
            return AgentUnavailable("trends_unavailable")
        text = " ".join(
            c.name + " " + " ".join(e.excerpt for e in c.evidence.citations)
            for c in candidates
        ).casefold()
        concepts: tuple[Concept, ...] = tuple(
            concept
            for concept in (
                "Italian cuisine",
                "Mexican cuisine",
                "Japanese cuisine",
                "Indian cuisine",
                "Korean cuisine",
                "Mediterranean cuisine",
                "fermentation",
                "noodles",
                "sourdough",
                "seafood",
                "barbecue",
                "coffee",
                "tea",
            )
            if concept.split()[0].casefold() in terms(text)
        )[:3] or ("seasonal cooking",)
        try:
            result = await self.tools.call(
                "search_food_trends",
                {"request": {"concepts": list(concepts), "geography": "California"}},
            )
            if not isinstance(result, TrendResult):
                raise ValueError("Invalid trend result")
            citations = trend_citations(result, self.clock())
            if not citations:
                return AgentUnavailable("trends_unavailable")

            def grounded_claims(draft: TrendDraft) -> tuple[TrendClaim, ...]:
                by_entity = {c.evidence.entity: c for c in candidates}
                by_citation = {c.id: c for c in citations}
                claims: list[TrendClaim] = []
                for item in draft.claims:
                    if (
                        instruction_span(item.claim)
                        or not trend_signal(item.claim)
                        or not supported_span(item.claim, citations, item.citation_ids)
                    ):
                        raise ValueError("Unsupported trend claim")
                    if any(
                        entity not in by_entity
                        or not (
                            terms(item.claim)
                            & terms(
                                " ".join(
                                    c.excerpt
                                    for c in by_entity[entity].evidence.citations
                                )
                            )
                        )
                        for entity in item.entities
                    ):
                        raise ValueError("Unsupported trend association")
                    claims.append(
                        TrendClaim(
                            item.claim,
                            item.entities,
                            tuple(by_citation[key] for key in item.citation_ids),
                        )
                    )
                if not claims:
                    raise ValueError("No grounded trend claims")
                return tuple(claims)

            options = grounded_options(candidates, citations)
            if not options:
                return AgentUnavailable("trends_unavailable")

            def validate(selection: TrendSelection) -> None:
                indices = selection.option_indices
                if (
                    not indices
                    or len(set(indices)) != len(indices)
                    or any(index >= len(options) for index in indices)
                ):
                    raise ValueError("Invalid grounded trend selection")

            selection = await structured(
                self.inference,
                TREND,
                {
                    "candidates": candidates,
                    "grounded_options": options,
                },
                TypeAdapter(TrendSelection),
                validate=validate,
            )
            claims = grounded_claims(
                TrendDraft(
                    claims=tuple(options[index] for index in selection.option_indices)
                )
            )
            # Revalidate freshness at the handoff, after inference latency.
            if (
                len(trend_citations(result, self.clock())) != len(citations)
                or not claims
            ):
                return AgentUnavailable("trends_unavailable")
            return AgentSuccess(
                TrendAnalysis(
                    tuple(claims),
                    ("Trends do not establish restaurant availability or nutrition",),
                )
            )
        except Exception:
            return AgentUnavailable("trends_unavailable")
