import json

import pytest

from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.application.workflow import TurnRequest
from food_recommender.domain.experts import AgentSuccess
from food_recommender.domain.values import Category


class Reply:
    def __init__(self, payload):
        self.payload = payload
        self.context = None

    async def generate(self, messages, schema, *, image=None):
        self.context = json.loads(messages[-1]["content"])
        return json.dumps(self.payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "categories", [["restaurant"], ["recipe"], ["restaurant", "recipe"]]
)
async def test_profile_intent_explicit_preferences_and_scoped_reviews(categories):
    provider = Reply({"categories": categories, "cuisines": ["Italian"]})
    outcome = await UserProfileGenerator(provider).run(
        TurnRequest(message="food please", explicit={"cuisines": ["Mexican"]}),
        reviews=("private review",),
    )
    assert isinstance(outcome, AgentSuccess)
    assert outcome.result.categories == tuple(Category(value) for value in categories)
    assert outcome.result.preferences.cuisines == ("Mexican",)
    assert provider.context["scoped_synthetic_reviews"] == []


@pytest.mark.asyncio
async def test_malformed_profile_fails_without_empty_restrictions():
    result = await UserProfileGenerator(Reply({"categories": []})).run(
        TurnRequest(message="food")
    )
    assert result.status == "failure"
