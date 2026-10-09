"""Even verbatim untrusted snippets cannot authorize unsupported safety/fact claims."""

from dataclasses import replace

import pytest
from scripts.phase10_acceptance import source_candidate
from tests.unit.agent_fixtures import Reply

from food_recommender.agents.nodes.recommendation import RecommendationExpert
from food_recommender.domain.experts import (
    AgentSuccess,
    AgentUnavailable,
    ProfileResult,
)
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import Category

BRANCHES = (
    AgentUnavailable("trends_unavailable"),
    AgentUnavailable("style_unavailable"),
    AgentUnavailable("nutrition_unavailable"),
)
CLAIMS = [
    "Guaranteed allergen-free and safe for every allergy.",
    "No cross-contact risk; safe for peanut allergies.",
    "Contains 30g protein and 200 calories per serving.",
    "Only 5 grams of carbohydrates per portion.",
    "The restaurant is open until midnight every day.",
    "Delivery is available today.",
    "Reservations are available tonight.",
    "This restaurant is currently viral and trending.",
    "Peanut-free meals with no risk.",
    "Sodium: 300 mg.",
    "Dinner costs $12.99 and has verified ratings.",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("claim", CLAIMS)
async def test_untrusted_excerpt_cannot_be_published_as_verified_claim(claim):
    food = source_candidate("restaurant", "1000002")
    citation = replace(food.evidence.citations[0], excerpt=claim)
    food = replace(food, evidence=replace(food.evidence, citations=(citation,)))
    provider = Reply(
        {
            "recommendations": [
                {
                    "entity": {"category": "restaurant", "id": food.evidence.entity.id},
                    "explanation": claim,
                    "citation_ids": [citation.id],
                }
            ]
        }
    )
    outcome = await RecommendationExpert(provider).run(
        ProfileResult((Category.RESTAURANT,), Preferences()), (food,), *BRANCHES
    )
    assert isinstance(outcome, AgentSuccess)
    assert outcome.result.recommendations == ()
    assert provider.calls == []


@pytest.mark.asyncio
async def test_unsafe_tool_limitations_are_not_published():
    food = source_candidate("recipe", "3")
    food = replace(
        food, evidence=replace(food.evidence, limitations=("Guaranteed allergen-free",))
    )
    provider = Reply({"recommendation_indices": [0]})
    outcome = await RecommendationExpert(provider).run(
        ProfileResult((Category.RECIPE,), Preferences()), (food,), *BRANCHES
    )
    assert outcome.status == "success"
    text = str(outcome.result)
    assert "Guaranteed" not in text and "200 calories" not in text
