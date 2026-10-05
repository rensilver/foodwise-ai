import json

import pytest

from food_recommender.agents.nodes.rag import RAGRetriever
from food_recommender.application.recommendations.workflow import TurnRequest
from food_recommender.domain.experts import AgentSuccess, ProfileResult
from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.values import Category, ConstraintKind, Origin, Strength
from food_recommender.retrieval.multimodal import MultimodalOutcome


class Planner:
    async def generate(self, messages, schema, *, image=None):
        return json.dumps({"query": "tomato basil", "include_reviews": True})


class Tools:
    def __init__(self, status="no_results"):
        self.calls = []
        self.status = status

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if self.status == "raise":
            raise RuntimeError("private provider details")
        return MultimodalOutcome(self.status, (), (), 1)


@pytest.mark.asyncio
async def test_three_attempts_keep_constraints_and_recipe_filters_scoped():
    hard = Constraint(ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT)
    profile = ProfileResult(
        (Category.RESTAURANT, Category.RECIPE),
        Preferences(constraints=(hard,), location="Silver Lake", price_band=2),
    )
    tools = Tools()
    result = await RAGRetriever(Planner(), tools).run(
        TurnRequest(message="food"), profile
    )
    assert isinstance(result.outcome, AgentSuccess)
    assert result.outcome.result.attempts == 3
    assert result.outcome.result.gaps
    assert len(tools.calls) == 6
    for name, args in tools.calls:
        request = args["request"]
        assert request["constraints"][0]["value"] == "peanut"
        assert request["include_reviews"] is False
        assert request["location"] == (
            "Silver Lake" if name == "search_restaurants" else None
        )


@pytest.mark.asyncio
async def test_tool_failure_is_not_empty_results():
    tools = Tools("raise")
    result = await RAGRetriever(Planner(), tools).run(
        TurnRequest(message="food"), ProfileResult((Category.RECIPE,), Preferences())
    )
    assert result.outcome.status == "failure"
    assert len(tools.calls) == 1
