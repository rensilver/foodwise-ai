import pytest
from tests.unit.agent_fixtures import Reply, candidate

from food_recommender.agents.nodes.recommendation import RecommendationExpert
from food_recommender.domain.experts import (
    AgentFailure,
    AgentSuccess,
    AgentUnavailable,
    ProfileResult,
)
from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.values import Category, ConstraintKind, Origin, Strength

PROFILE = ProfileResult((Category.RECIPE,), Preferences())
BRANCHES = (
    AgentUnavailable("trends_unavailable"),
    AgentUnavailable("style_unavailable"),
    AgentUnavailable("nutrition_unavailable"),
)


@pytest.mark.asyncio
async def test_unknown_ids_and_citations_get_one_repair_then_fail():
    food = candidate()
    for identity, citation in (
        ("unknown", food.evidence.citations[0].id),
        (food.evidence.entity.id, "invented"),
    ):
        provider = Reply(
            {
                "recommendations": [
                    {
                        "entity": {"category": "recipe", "id": identity},
                        "explanation": food.evidence.citations[0].excerpt,
                        "citation_ids": [citation],
                    }
                ]
            }
        )
        result = await RecommendationExpert(provider).run(PROFILE, (food,), *BRANCHES)
        assert isinstance(result, AgentFailure)
        assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_supported_recommendation_uses_all_outcomes_and_records_degradation():
    food = candidate()
    provider = Reply(
        {
            "recommendations": [
                {
                    "entity": {"category": "recipe", "id": food.evidence.entity.id},
                    "explanation": food.evidence.citations[0].excerpt,
                    "citation_ids": [food.evidence.citations[0].id],
                }
            ]
        }
    )
    result = await RecommendationExpert(provider).run(PROFILE, (food,), *BRANCHES)
    assert isinstance(result, AgentSuccess)
    assert len(result.result.recommendations) == 1
    assert len(result.result.limitations) >= 3
    assert all(key in provider.calls[0] for key in ("trend", "style", "nutrition"))


@pytest.mark.asyncio
async def test_unknown_allergen_compliance_withholds_without_unsafe_fallback():
    profile = ProfileResult(
        (Category.RECIPE,),
        Preferences(
            constraints=(
                Constraint(
                    ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT
                ),
            )
        ),
    )
    provider = Reply({"recommendations": []})
    result = await RecommendationExpert(provider).run(
        profile, (candidate(),), *BRANCHES
    )
    assert result.result.recommendations == ()
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observation", ["tomato rice simmered with basil", "invented spicy flavor"]
)
async def test_style_guidance_is_rechecked_against_the_candidate_before_synthesis(
    observation,
):
    import json

    from food_recommender.domain.experts import StyleAnalysis, StyleAssessment
    from food_recommender.domain.values import EvidenceState

    food = candidate()
    style = AgentSuccess(
        StyleAnalysis(
            (
                StyleAssessment(
                    food.evidence.entity,
                    EvidenceState.SUPPORTED,
                    (food.evidence.citations[0].id,),
                    (observation,),
                ),
            )
        )
    )
    seen = []

    class GuidedReply:
        async def generate(self, messages, schema, *, image=None):
            context = json.loads(messages[1]["content"])
            seen.append(context["grounded_recommendations"])
            return json.dumps({"recommendations": context["grounded_recommendations"]})

    result = await RecommendationExpert(GuidedReply()).run(
        PROFILE, (food,), BRANCHES[0], style, BRANCHES[2]
    )
    assert result.status == "success"
    if observation.startswith("invented"):
        assert seen == [[]]
        assert not result.result.recommendations
    else:
        assert result.result.recommendations[0].explanation == observation
        assert result.result.recommendations[0].citation_ids == (
            food.evidence.citations[0].id,
        )
