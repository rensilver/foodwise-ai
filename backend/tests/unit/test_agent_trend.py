from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from tests.unit.agent_fixtures import Reply, candidate

from food_recommender.agents.nodes.trend import FoodTrendAnalyst
from food_recommender.application.trends.ports import TrendItem
from food_recommender.application.trends.service import TrendResult
from food_recommender.domain.experts import AgentSuccess, ProfileResult
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import Category

NOW = datetime(2026, 10, 4, tzinfo=UTC)
PROFILE = ProfileResult((Category.RECIPE,), Preferences())


class Trends:
    def __init__(self, days=1):
        self.days = days
        self.calls = []
        self.identity = uuid4()

    async def call(self, name, arguments):
        self.calls.append(arguments)
        return TrendResult(
            status="available",
            evidence=(
                TrendItem(
                    self.identity,
                    "https://example.test/italian",
                    "Italian rice dishes are popular",
                    NOW.date() - timedelta(days=self.days),
                    NOW,
                ),
            ),
        )


@pytest.mark.asyncio
async def test_dated_claim_has_real_candidate_association_and_public_query_only():
    tools = Trends()
    food = candidate()
    provider = Reply({"option_indices": [0]})
    result = await FoodTrendAnalyst(provider, tools, clock=lambda: NOW).run(
        PROFILE, (food,)
    )
    assert isinstance(result, AgentSuccess)
    assert result.result.claims[0].citations[0].published_on == NOW.date() - timedelta(
        days=1
    )
    assert set(tools.calls[0]["request"]) == {"concepts", "geography"}


@pytest.mark.asyncio
async def test_stale_evidence_and_unsupported_claims_are_unavailable():
    food = candidate()
    for days in (100, 1):
        tools = Trends(days)
        provider = Reply(
            {
                "claims": [
                    {
                        "claim": "invented claim",
                        "entities": [
                            {"category": "recipe", "id": food.evidence.entity.id}
                        ],
                        "citation_ids": [str(tools.identity)],
                    }
                ]
            }
        )
        result = await FoodTrendAnalyst(provider, tools, clock=lambda: NOW).run(
            PROFILE, (food,)
        )
        assert result.status == "unavailable"


@pytest.mark.asyncio
async def test_dated_price_evidence_does_not_become_a_food_trend_claim():
    class Prices(Trends):
        async def call(self, name, arguments):
            return TrendResult(
                status="available",
                evidence=(
                    TrendItem(
                        self.identity,
                        "https://example.test/prices",
                        "Italian rice costs ten dollars",
                        NOW.date(),
                        NOW,
                    ),
                ),
            )

    tools = Prices()
    food = candidate()
    provider = Reply(
        {
            "claims": [
                {
                    "claim": "Italian rice costs ten dollars",
                    "entities": [{"category": "recipe", "id": food.evidence.entity.id}],
                    "citation_ids": [str(tools.identity)],
                }
            ]
        }
    )
    result = await FoodTrendAnalyst(provider, tools, clock=lambda: NOW).run(
        PROFILE, (food,)
    )
    assert result.status == "unavailable"


@pytest.mark.asyncio
async def test_trend_repairs_nested_schema_and_ungrounded_claim_without_new_search():
    import json

    from food_recommender.application.recommendations.reliability import (
        RunBudget,
        RunLimits,
        current_budget,
    )

    tools, food = Trends(), candidate()
    calls = []

    class RepairReply:
        async def generate(self, messages, schema, *, image=None):
            calls.append(messages)
            claim = {
                "claim": "Italian rice dishes are popular",
                "entities": [{"category": "recipe", "id": food.evidence.entity.id}],
                "citation_ids": [str(tools.identity)],
            }
            if len(calls) == 1:
                return json.dumps({"option_indices": {"nested": claim}})
            if len(calls) == 2:
                assert "option_indices" in messages[-1]["content"]
                return json.dumps({"option_indices": [4]})
            return json.dumps({"option_indices": [0]})

    token = current_budget.set(RunBudget(RunLimits(schema_repairs=2)))
    try:
        result = await FoodTrendAnalyst(RepairReply(), tools, clock=lambda: NOW).run(
            PROFILE, (food,)
        )
    finally:
        current_budget.reset(token)
    assert result.status == "success"
    assert len(calls) == 3
    assert len(tools.calls) == 1
    assert result.result.claims[0].claim == "Italian rice dishes are popular"


@pytest.mark.asyncio
async def test_trend_offers_exact_eligible_spans_without_invented_connecting_text():
    import json
    from dataclasses import replace

    text = "Italian rice dishes are served here.\n\nThis cuisine is growing popular."

    class Evidence(Trends):
        async def call(self, name, arguments):
            result = await super().call(name, arguments)
            return result.model_copy(
                update={"evidence": (replace(result.evidence[0], excerpt=text),)}
            )

    class Selector:
        async def generate(self, messages, schema, *, image=None):
            context = json.loads(messages[1]["content"])
            assert context["grounded_options"][0]["claim"] == text
            return json.dumps({"option_indices": [0]})

    result = await FoodTrendAnalyst(Selector(), Evidence(), clock=lambda: NOW).run(
        PROFILE, (candidate(),)
    )
    assert result.status == "success"
    assert result.result.claims[0].claim == text
