"""Typed source plans; tools and immutable hard filters are controlled in code."""

from dataclasses import dataclass, replace

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from pydantic_core import to_jsonable_python

from food_recommender.agents.prompts import RAG
from food_recommender.agents.structured import structured
from food_recommender.application.inference import Inference
from food_recommender.application.workflow import ToolGateway, TurnRequest
from food_recommender.domain.experts import (
    AgentFailure,
    AgentSuccess,
    ExpertOutcome,
    ProfileResult,
    RetrievalResult,
)
from food_recommender.domain.values import Category
from food_recommender.retrieval.dietary import assess, eligible
from food_recommender.retrieval.fusion import RankedTextCandidate
from food_recommender.retrieval.late_fusion import FusedCandidate, late_fuse
from food_recommender.retrieval.models import ImageHit
from food_recommender.retrieval.multimodal import MultimodalOutcome


class SourcePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    include_reviews: bool = False
    use_images: bool = False


@dataclass(frozen=True)
class RetrievedData:
    outcome: ExpertOutcome[RetrievalResult]
    catalog: tuple[FusedCandidate, ...] = ()


def fuse_sources(
    text: tuple[FusedCandidate, ...],
    images: tuple[FusedCandidate, ...],
    category: Category,
) -> tuple[FusedCandidate, ...]:
    """Reuse canonical late fusion; CLIP evidence never masquerades as text."""
    ranked = tuple(
        RankedTextCandidate(
            c.evidence,
            c.name,
            c.ingredients,
            c.allergens,
            c.lexical_score,
            c.text_cosine_similarity,
            c.rrf_score if c.rrf_score is not None else c.evidence.relevance,
            c.assessments,
        )
        for c in text
        if c.evidence.entity.category == category
    )
    image_hits = tuple(
        ImageHit(
            c.evidence.entity,
            c.name,
            citation,
            media_id,
            c.image_cosine_similarity
            if c.image_cosine_similarity is not None
            else c.evidence.relevance,
            c.ingredients,
            c.allergens,
        )
        for c in images
        if c.evidence.entity.category == category
        for citation in c.evidence.citations
        for media_id in c.media_ids
    )
    return late_fuse(ranked, image_hits, 20).candidates


class RAGRetriever:
    def __init__(
        self, inference: Inference, tools: ToolGateway, *, minimum_per_category: int = 1
    ) -> None:
        if not 1 <= minimum_per_category <= 20:
            raise ValueError("Invalid sufficiency target")
        self.inference, self.tools = inference, tools
        self.minimum = minimum_per_category

    async def run(self, request: TurnRequest, profile: ProfileResult) -> RetrievedData:
        found: dict[tuple[Category, str], FusedCandidate] = {}
        gaps: tuple[str, ...] = ()
        for attempt in range(1, 4):
            try:
                plan = await structured(
                    self.inference,
                    RAG,
                    {
                        "message": request.message,
                        "profile": profile,
                        "attempt": attempt,
                        "gaps": gaps,
                    },
                    TypeAdapter(SourcePlan),
                )
            except Exception:
                return RetrievedData(AgentFailure("invalid_response"))
            try:
                for category in profile.categories:
                    preferences = profile.preferences
                    arguments = {
                        "query": plan.query,
                        "limit": 20,
                        "cuisine": preferences.cuisines[0]
                        if len(preferences.cuisines) == 1
                        else None,
                        "location": preferences.location
                        if category == Category.RESTAURANT
                        else None,
                        "max_price_band": preferences.price_band
                        if category == Category.RESTAURANT
                        else None,
                        "constraints": to_jsonable_python(preferences.constraints),
                        "include_reviews": bool(
                            plan.include_reviews
                            and request.demo_profile_id
                            and category == Category.RESTAURANT
                        ),
                    }
                    tool = (
                        "search_restaurants"
                        if category == Category.RESTAURANT
                        else "search_recipes"
                    )
                    text = await self.tools.call(tool, {"request": arguments})
                    if not isinstance(text, MultimodalOutcome) or text.status in {
                        "dependency_error",
                        "invalid_request",
                    }:
                        return RetrievedData(AgentFailure("dependency_unavailable"))
                    image_candidates: tuple[FusedCandidate, ...] = ()
                    if request.media_id or plan.use_images:
                        image = await self.tools.call(
                            "search_images",
                            {
                                "request": {
                                    **arguments,
                                    "category": category.value,
                                    "media_id": request.media_id,
                                }
                            },
                        )
                        if not isinstance(image, MultimodalOutcome) or image.status in {
                            "dependency_error",
                            "invalid_request",
                        }:
                            # Requested image failure cannot silently become a text answer.
                            return RetrievedData(AgentFailure("dependency_unavailable"))
                        image_candidates = image.candidates
                    for candidate in fuse_sources(
                        text.candidates, image_candidates, category
                    ):
                        checks = tuple(
                            assess(c, candidate.ingredients, candidate.allergens)
                            for c in preferences.constraints
                        )
                        if not eligible(checks):
                            continue
                        key = (category, candidate.evidence.entity.id)
                        candidate = replace(candidate, assessments=checks)
                        if (
                            key not in found
                            or candidate.evidence.relevance
                            > found[key].evidence.relevance
                        ):
                            found[key] = candidate
                gaps = tuple(
                    f"Insufficient {category.value} evidence under unchanged constraints"
                    for category in profile.categories
                    if sum(key[0] == category for key in found) < self.minimum
                )
                if not gaps:
                    break
            except Exception:
                return RetrievedData(AgentFailure("dependency_unavailable"))
        catalog = tuple(
            candidate
            for category in profile.categories
            for candidate in sorted(
                (c for c in found.values() if c.evidence.entity.category == category),
                key=lambda c: (-c.evidence.relevance, c.evidence.entity.id),
            )[:20]
        )
        return RetrievedData(
            AgentSuccess(
                RetrievalResult(tuple(c.evidence for c in catalog), attempt, gaps)
            ),
            catalog,
        )
