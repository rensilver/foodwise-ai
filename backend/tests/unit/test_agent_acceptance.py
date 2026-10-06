"""Observable full six-role behavior using source fixtures and fake boundaries."""

import json
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from tests.unit.agent_fixtures import candidate
from tests.unit.test_agent_runner import Leases

from food_recommender.agents.graph import WorkflowRoles, build_graph
from food_recommender.agents.nodes.nutrition import NutritionExpert
from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.agents.nodes.rag import RAGRetriever
from food_recommender.agents.nodes.recommendation import RecommendationExpert
from food_recommender.agents.nodes.style import FoodStyleExpert
from food_recommender.agents.nodes.trend import FoodTrendAnalyst
from food_recommender.agents.runner import GraphRunner
from food_recommender.application.recommendations.contracts import (
    recommendation_outcome_adapter,
)
from food_recommender.application.recommendations.reliability import BudgetedInference
from food_recommender.application.recommendations.workflow import TurnRequest
from food_recommender.application.trends.service import TrendResult
from food_recommender.domain.experts import AgentSuccess
from food_recommender.domain.values import Category
from food_recommender.retrieval.multimodal import MultimodalOutcome


class CulinaryReply:
    def __init__(self, *, broken_profile=False, broken_style=False):
        self.calls = []
        self.broken_profile, self.broken_style = broken_profile, broken_style

    async def generate(self, messages, schema, *, image=None):
        context = json.loads(messages[1]["content"])
        self.calls.append((messages[0]["content"], context))
        if "request" in context:
            return (
                "not JSON"
                if self.broken_profile
                else json.dumps({"categories": ["restaurant", "recipe"]})
            )
        if "attempt" in context:
            return json.dumps({"query": "Italian tomato rice"})
        if "deterministic_assessments" in context:
            return json.dumps({"assessments": context["deterministic_assessments"]})
        if "eligible_candidates" in context:
            items = []
            counts = {}
            for c in context["eligible_candidates"]:
                entity = c["evidence"]["entity"]
                category = entity["category"]
                counts[category] = counts.get(category, 0) + 1
                if counts[category] > 5:
                    continue
                citation = c["evidence"]["citations"][0]
                items.append(
                    {
                        "entity": entity,
                        "explanation": citation["excerpt"],
                        "citation_ids": [citation["id"]],
                    }
                )
            return json.dumps({"recommendations": items})
        if "candidates" in context:
            if self.broken_style:
                raise RuntimeError("private provider response")
            return json.dumps(
                {
                    "selections": [
                        {
                            "candidate_index": index,
                            "option_index": 0
                            if context["grounded_options"][index]
                            else None,
                        }
                        for index, _ in enumerate(context["candidates"])
                    ]
                }
            )
        raise AssertionError("Unexpected inference call")


class CatalogTools:
    def __init__(self):
        self.calls = []

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search_food_trends":
            return TrendResult(status="unavailable", reason="missing_credentials")
        category = (
            Category.RESTAURANT if name == "search_restaurants" else Category.RECIPE
        )
        return MultimodalOutcome(
            "success",
            tuple(
                candidate(f"{category}:{i:02}", category=category) for i in range(20)
            ),
            (),
            1,
        )


def runner_for(provider, tools, owner, conversation):
    inference = BudgetedInference(provider)
    roles = WorkflowRoles(
        UserProfileGenerator(inference),
        RAGRetriever(inference, tools),
        FoodTrendAnalyst(inference, tools),
        FoodStyleExpert(inference),
        NutritionExpert(inference),
        RecommendationExpert(inference),
    )
    return GraphRunner(
        build_graph(roles, checkpointer=InMemorySaver()), Leases(owner, conversation)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("broken_style", [False, True])
async def test_all_roles_cover_forty_candidates_and_synthesis_handles_unavailable_branch(
    broken_style,
):
    owner, conversation = uuid4(), uuid4()
    provider, tools = CulinaryReply(broken_style=broken_style), CatalogTools()
    runner = runner_for(provider, tools, owner, conversation)
    result = await runner.run(
        owner, conversation, TurnRequest(message="Italian tomato rice")
    )
    final = recommendation_outcome_adapter.validate_json(json.dumps(result["final"]))
    assert isinstance(final, AgentSuccess)
    assert len(final.result.recommendations) == 10
    assert len(result["catalog"]) == 40
    assert len(result["nutrition"]["result"]["assessments"]) == 40
    if not broken_style:
        assert len(result["style"]["result"]["assessments"]) == 40
    else:
        assert result["style"]["status"] == "unavailable"
    synthesis = [c for prompt, c in provider.calls if "eligible_candidates" in c]
    assert len(synthesis) == 1
    assert len(synthesis[0]["eligible_candidates"]) == 40
    assert {m["stage"] for m in result["metrics"]["stages"]} == {
        "profile",
        "retrieval",
        "trend",
        "style",
        "nutrition",
        "recommendation",
    }
    assert result["metrics"]["retrieval_attempts"] == 1
    allowed = {c["evidence"]["entity"]["id"] for c in result["catalog"]}
    assert all(r.entity.id in allowed for r in final.result.recommendations)


@pytest.mark.asyncio
async def test_profile_invalid_json_has_two_schema_repairs_and_no_downstream_calls():
    owner, conversation = uuid4(), uuid4()
    provider, tools = CulinaryReply(broken_profile=True), CatalogTools()
    result = await runner_for(provider, tools, owner, conversation).run(
        owner, conversation, TurnRequest(message="rice")
    )
    assert result["profile_outcome"]["status"] == "failure"
    assert len(provider.calls) == 3
    assert tools.calls == []
    assert result["catalog"] == []
    assert result["final"]["status"] == "failure"
    assert result["errors"][0]["stage"] == "profile_outcome"
