import json

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
    provider = Reply({"recommendation_indices": [0]})
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
            return json.dumps({"recommendation_indices": [0]})

    result = await RecommendationExpert(GuidedReply()).run(
        PROFILE, (food,), BRANCHES[0], style, BRANCHES[2]
    )
    assert result.status == "success"
    if observation.startswith("invented"):
        assert len(seen[0]) == 1
        assert (
            result.result.recommendations[0].explanation
            == food.evidence.citations[0].excerpt
        )
        assert observation not in result.result.recommendations[0].explanation
    else:
        assert result.result.recommendations[0].explanation == observation
        assert result.result.recommendations[0].citation_ids == (
            food.evidence.citations[0].id,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["schema", "explanation"])
async def test_repair_receives_specific_validation_feedback(failure):
    food = candidate()
    contexts = []

    class RepairReply:
        async def generate(self, messages, schema, *, image=None):
            context = json.loads(messages[1]["content"])
            contexts.append(context)
            if len(contexts) == 1:
                if failure == "schema":
                    return json.dumps({"recommendation_indices": "not an array"})
                return json.dumps(
                    {
                        "recommendations": [
                            {
                                "entity": {
                                    "category": "recipe",
                                    "id": food.evidence.entity.id,
                                },
                                "explanation": "invented spicy flavor",
                                "citation_ids": [food.evidence.citations[0].id],
                            }
                        ]
                    }
                )
            feedback = context["repair"]
            assert "recommendation" in feedback
            if failure == "schema":
                assert "tuple_type" in feedback
                assert "array" in feedback
                assert "not an array" not in feedback
            else:
                assert "extra_forbidden" in feedback
                assert "recommendations" in feedback
            return json.dumps({"recommendation_indices": [0]})

    result = await RecommendationExpert(RepairReply()).run(PROFILE, (food,), *BRANCHES)
    assert isinstance(result, AgentSuccess)
    assert len(contexts) == 2
    assert len(result.result.recommendations) == 1
    assert (
        result.result.recommendations[0].explanation
        == food.evidence.citations[0].excerpt
    )


@pytest.mark.asyncio
async def test_style_unavailable_still_supplies_verified_catalog_quotations():
    food = candidate()

    class CatalogReply:
        async def generate(self, messages, schema, *, image=None):
            return json.dumps({"recommendation_indices": [0]})

    result = await RecommendationExpert(CatalogReply()).run(PROFILE, (food,), *BRANCHES)
    assert isinstance(result, AgentSuccess)
    assert len(result.result.recommendations) == 1
    assert (
        result.result.recommendations[0].explanation
        == food.evidence.citations[0].excerpt
    )
    assert "Style analysis unavailable" in result.result.limitations


@pytest.mark.asyncio
async def test_repeated_unsupported_explanation_is_never_published():
    food = candidate()
    provider = Reply(
        {
            "recommendations": [
                {
                    "entity": {"category": "recipe", "id": food.evidence.entity.id},
                    "explanation": "invented spicy flavor",
                    "citation_ids": [food.evidence.citations[0].id],
                }
            ]
        }
    )
    result = await RecommendationExpert(provider).run(PROFILE, (food,), *BRANCHES)
    assert isinstance(result, AgentFailure)
    assert len(provider.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("indices", [[1], [-1], [0, 0], [True], ["0"]])
async def test_invalid_selections_fail_closed_after_one_repair(indices):
    provider = Reply({"recommendation_indices": indices})
    result = await RecommendationExpert(provider).run(
        PROFILE, (candidate(),), *BRANCHES
    )
    assert isinstance(result, AgentFailure)
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_more_than_five_selections_in_one_category_are_rejected():
    foods = tuple(candidate(f"recipe:{i}") for i in range(6))
    provider = Reply({"recommendation_indices": list(range(6))})
    result = await RecommendationExpert(provider).run(PROFILE, foods, *BRANCHES)
    assert isinstance(result, AgentFailure)
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_out_of_range_selection_repair_then_preserves_model_order():
    foods = (candidate("recipe:1"), candidate("recipe:2"))
    calls = []

    class SelectionReply:
        async def generate(self, messages, schema, *, image=None):
            context = json.loads(messages[1]["content"])
            calls.append(context)
            assert [
                option["recommendation_index"]
                for option in context["grounded_recommendations"]
            ] == [0, 1]
            if len(calls) == 1:
                return json.dumps({"recommendation_indices": [2]})
            assert "[0, 1]" in context["repair"]
            return json.dumps({"recommendation_indices": [1, 0]})

    result = await RecommendationExpert(SelectionReply()).run(PROFILE, foods, *BRANCHES)
    assert isinstance(result, AgentSuccess)
    assert [item.entity for item in result.result.recommendations] == [
        food.evidence.entity for food in reversed(foods)
    ]
    assert len(calls) == 2
