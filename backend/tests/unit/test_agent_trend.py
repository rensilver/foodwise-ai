from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from tests.unit.agent_fixtures import Reply, candidate

from food_recommender.agents.nodes.trend import FoodTrendAnalyst
from food_recommender.application.ports import TrendItem
from food_recommender.application.trends import TrendResult
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
    provider = Reply(
        {
            "claims": [
                {
                    "claim": "Italian rice dishes are popular",
                    "entities": [{"category": "recipe", "id": food.evidence.entity.id}],
                    "citation_ids": [str(tools.identity)],
                }
            ]
        }
    )
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
