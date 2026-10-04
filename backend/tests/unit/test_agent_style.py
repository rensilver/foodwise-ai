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
                "assessments": [
                    {
                        "entity": c["evidence"]["entity"],
                        "state": "supported",
                        "citation_ids": [c["evidence"]["citations"][0]["id"]],
                        "observations": ["tomato rice simmered with basil"],
                    }
                    for c in context["candidates"]
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
