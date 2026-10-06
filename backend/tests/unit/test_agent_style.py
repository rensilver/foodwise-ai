import json

import pytest
from tests.unit.agent_fixtures import Reply, candidate

from food_recommender.agents.nodes.style import FoodStyleExpert
from food_recommender.domain.experts import AgentSuccess, ProfileResult
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import Category


class StyleReply(Reply):
    async def generate(self, messages, schema, *, image=None):
        context = json.loads(messages[-1]["content"])
        self.calls.append(context)
        return json.dumps(
            {
                "selections": [
                    {"candidate_index": index, "option_index": 0}
                    for index, _ in enumerate(context["candidates"])
                ]
            }
        )


@pytest.mark.asyncio
async def test_all_twenty_candidates_are_analyzed_with_bounded_batches():
    provider = StyleReply(None)
    candidates = tuple(candidate(f"recipe:{i}") for i in range(20))
    result = await FoodStyleExpert(provider, batch_size=7).run(
        ProfileResult((Category.RECIPE,), Preferences()), candidates
    )
    assert isinstance(result, AgentSuccess)
    assert len(result.result.assessments) == 20
    assert [len(c["candidates"]) for c in provider.calls] == [7, 7, 6]


@pytest.mark.asyncio
async def test_unsupported_style_and_provider_failure_are_unavailable():
    food = candidate()
    for payload in (
        "not JSON",
        {
            "assessments": [
                {
                    "entity": {"category": "recipe", "id": food.evidence.entity.id},
                    "state": "supported",
                    "citation_ids": [food.evidence.citations[0].id],
                    "observations": ["invented spicy flavor"],
                }
            ]
        },
    ):
        result = await FoodStyleExpert(Reply(payload)).run(
            ProfileResult((Category.RECIPE,), Preferences()), (food,)
        )
        assert result.status == "unavailable"


@pytest.mark.asyncio
async def test_ungrounded_style_is_repaired_within_the_shared_budget():
    from food_recommender.application.recommendations.reliability import (
        RunBudget,
        RunLimits,
        current_budget,
    )

    food = candidate()

    class RepairReply:
        def __init__(self):
            self.calls = 0

        async def generate(self, messages, schema, *, image=None):
            self.calls += 1
            return json.dumps(
                {
                    "selections": [
                        {
                            "candidate_index": 0,
                            "option_index": 11 if self.calls == 1 else 0,
                        }
                    ]
                }
            )

    provider = RepairReply()
    token = current_budget.set(RunBudget(RunLimits(schema_repairs=1)))
    try:
        result = await FoodStyleExpert(provider).run(
            ProfileResult((Category.RECIPE,), Preferences()), (food,)
        )
    finally:
        current_budget.reset(token)
    assert result.status == "success"
    assert provider.calls == 2
    assert result.result.assessments[0].observations == (
        food.evidence.citations[0].excerpt,
    )


@pytest.mark.asyncio
async def test_repeated_ungrounded_style_exhausts_repairs_without_publishing():
    from food_recommender.application.recommendations.reliability import (
        RunBudget,
        RunLimits,
        current_budget,
    )

    food = candidate()
    calls = []

    class UngroundedReply:
        async def generate(self, messages, schema, *, image=None):
            calls.append(messages)
            return json.dumps(
                {
                    "assessments": [
                        {
                            "entity": {
                                "category": "recipe",
                                "id": food.evidence.entity.id,
                            },
                            "state": "supported",
                            "citation_ids": [food.evidence.citations[0].id],
                            "observations": ["invented spicy flavor"],
                        }
                    ]
                }
            )

    token = current_budget.set(RunBudget(RunLimits(schema_repairs=1)))
    try:
        result = await FoodStyleExpert(UngroundedReply()).run(
            ProfileResult((Category.RECIPE,), Preferences()), (food,)
        )
    finally:
        current_budget.reset(token)
    assert result.status == "unavailable"
    assert len(calls) == 2
