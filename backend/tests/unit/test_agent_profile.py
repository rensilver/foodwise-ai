import json

import pytest

from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.application.recommendations.workflow import TurnRequest
from food_recommender.domain.experts import AgentSuccess, ProfileResult
from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.values import Category, ConstraintKind, Origin, Strength


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


HARD = Constraint(ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT)
PRIOR = ProfileResult((Category.RECIPE,), Preferences(constraints=(HARD,)))


@pytest.mark.asyncio
async def test_ambiguous_model_removal_clarifies_and_retains_restrictions():
    provider = Reply(
        {
            "changes": [
                {
                    "operation": "remove",
                    "constraint": {
                        "kind": "allergen",
                        "value": "peanut",
                        "strength": "hard",
                        "origin": "explicit",
                    },
                    "evidence": "peanut",
                }
            ]
        }
    )
    outcome = await UserProfileGenerator(provider).run(
        TurnRequest(message="peanut"), PRIOR
    )
    assert outcome.result.preferences.constraints == (HARD,)
    assert outcome.result.clarification


@pytest.mark.asyncio
async def test_explicit_correction_can_remove_but_omission_cannot():
    generator = UserProfileGenerator(Reply({}))
    outcome = await generator.run(TurnRequest(message="now Italian"), PRIOR)
    assert outcome.result.preferences.constraints == (HARD,)
    corrected = await generator.run(
        TurnRequest(
            message="correct my profile",
            explicit={"remove_constraints": [{"kind": "allergen", "value": "peanut"}]},
        ),
        PRIOR,
    )
    assert corrected.result.preferences.constraints == ()


@pytest.mark.asyncio
async def test_inference_cannot_downgrade_known_hard_constraint():
    provider = Reply(
        {
            "changes": [
                {
                    "operation": "add",
                    "constraint": {
                        "kind": "allergen",
                        "value": "peanut",
                        "strength": "soft",
                        "origin": "inferred",
                    },
                    "evidence": "peanut",
                }
            ]
        }
    )
    result = await UserProfileGenerator(provider).run(
        TurnRequest(message="peanut"), PRIOR
    )
    assert result.result.preferences.constraints == (HARD,)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value,message",
    [
        ("none", "Now recommend a Korean recipe like this image."),
        ("soy", "Soy tastes good."),
    ],
)
async def test_model_cannot_invent_hard_restrictions_from_an_unrelated_quote(
    value, message
):
    provider = Reply(
        {
            "changes": [
                {
                    "operation": "add",
                    "constraint": {
                        "kind": "allergen",
                        "value": value,
                        "strength": "hard",
                        "origin": "explicit",
                    },
                    "evidence": message,
                }
            ]
        }
    )
    result = await UserProfileGenerator(provider).run(
        TurnRequest(message=message), PRIOR
    )
    assert result.status == "failure"
    assert PRIOR.preferences.constraints == (HARD,)


@pytest.mark.asyncio
async def test_named_allergy_is_added_without_erasing_a_prior_restriction():
    provider = Reply(
        {
            "changes": [
                {
                    "operation": "add",
                    "constraint": {
                        "kind": "allergen",
                        "value": "soy",
                        "strength": "hard",
                        "origin": "explicit",
                    },
                    "evidence": "I have a soy allergy",
                }
            ]
        }
    )
    result = await UserProfileGenerator(provider).run(
        TurnRequest(message="I have a soy allergy"), PRIOR
    )
    assert result.status == "success"
    assert {c.value for c in result.result.preferences.constraints} == {"peanut", "soy"}


@pytest.mark.asyncio
async def test_negated_allergy_cannot_become_an_added_hard_restriction():
    provider = Reply(
        {
            "changes": [
                {
                    "operation": "add",
                    "constraint": {
                        "kind": "allergen",
                        "value": "soy",
                        "strength": "hard",
                        "origin": "explicit",
                    },
                    "evidence": "I am not allergic to soy",
                }
            ]
        }
    )
    result = await UserProfileGenerator(provider).run(
        TurnRequest(message="I am not allergic to soy"), PRIOR
    )
    assert result.status == "failure"
