import pytest
from tests.unit.agent_fixtures import Reply, candidate

from food_recommender.agents.nodes.nutrition import NutritionExpert
from food_recommender.domain.experts import AgentSuccess, ProfileResult
from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.values import (
    Category,
    ConstraintKind,
    EvidenceState,
    Origin,
    Strength,
)


@pytest.mark.asyncio
async def test_conflicts_and_unknowns_survive_llm_reassurance():
    restriction = Constraint(
        ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT
    )
    foods = (
        candidate("recipe:conflict", ingredients=("peanut",)),
        candidate("recipe:unknown", ingredients=("rice",)),
    )
    provider = Reply(
        {
            "assessments": [
                {
                    "entity": {"category": "recipe", "id": c.evidence.entity.id},
                    "state": "supported",
                    "citation_ids": [c.evidence.citations[0].id],
                    "limitations": [],
                }
                for c in foods
            ]
        }
    )
    result = await NutritionExpert(provider).run(
        ProfileResult((Category.RECIPE,), Preferences(constraints=(restriction,))),
        foods,
    )
    assert isinstance(result, AgentSuccess)
    assert [a.state for a in result.result.assessments] == [
        EvidenceState.CONFLICTING,
        EvidenceState.UNKNOWN,
    ]
    assert all(
        "Structured nutrition analysis unavailable" in a.limitations
        for a in result.result.assessments
    )


@pytest.mark.asyncio
async def test_deterministic_simple_plant_diet_survives_provider_failure():
    restriction = Constraint(
        ConstraintKind.DIETARY, "vegan", Strength.HARD, Origin.EXPLICIT
    )
    foods = tuple(candidate(f"recipe:{i}") for i in range(20))
    result = await NutritionExpert(Reply("invalid JSON"), batch_size=6).run(
        ProfileResult((Category.RECIPE,), Preferences(constraints=(restriction,))),
        foods,
    )
    assert isinstance(result, AgentSuccess)
    assert len(result.result.assessments) == 20
    assert all(a.state == EvidenceState.SUPPORTED for a in result.result.assessments)
