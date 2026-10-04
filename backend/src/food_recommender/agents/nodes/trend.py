"""Dated, relevant public MCP evidence; no private query context crosses the wire."""

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from food_recommender.agents.prompts import TREND
from food_recommender.agents.structured import structured
from food_recommender.application.evidence_rules import (
    supported_span,
    terms,
    trend_signal,
)
from food_recommender.application.inference import Inference
from food_recommender.application.trends import Concept, TrendResult, trend_citations
from food_recommender.application.workflow import ToolGateway
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
            draft = await structured(
                self.inference,
                TREND,
                {"candidates": candidates, "dated_evidence": citations},
                TypeAdapter(TrendDraft),
            )
            by_entity = {c.evidence.entity: c for c in candidates}
            by_citation = {c.id: c for c in citations}
            claims = []
            for item in draft.claims:
                if not trend_signal(item.claim) or not supported_span(
                    item.claim, citations, item.citation_ids
                ):
                    raise ValueError("Unsupported trend claim")
                if any(
                    entity not in by_entity
                    or not (
                        terms(item.claim)
                        & terms(
                            " ".join(
                                c.excerpt for c in by_entity[entity].evidence.citations
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
