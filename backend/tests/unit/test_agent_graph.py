import asyncio
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from tests.unit.agent_fixtures import candidate

from food_recommender.agents.graph import WorkflowRoles, build_graph
from food_recommender.agents.nodes.rag import RetrievedData
from food_recommender.domain.experts import (
    AgentSuccess,
    AgentUnavailable,
    ProfileResult,
    RetrievalResult,
)
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.recommendations import RecommendationResult
from food_recommender.domain.values import Category


class Profile:
    async def run(self, request, prior=None, **kwargs):
        return AgentSuccess(ProfileResult((Category.RECIPE,), Preferences()))


class Retrieval:
    async def run(self, request, profile):
        food = candidate()
        return RetrievedData(
            AgentSuccess(RetrievalResult((food.evidence,), 1)), (food,)
        )


class Branch:
    def __init__(self, kind, started, ready):
        self.kind, self.started, self.ready = kind, started, ready
        self.finished = False

    async def run(self, *args):
        self.started.add(self.kind)
        if len(self.started) == 3:
            self.ready.set()
        await asyncio.wait_for(self.ready.wait(), 1)
        await asyncio.sleep(0.01)
        self.finished = True
        return AgentUnavailable(f"{self.kind}_unavailable")


class Synthesis:
    def __init__(self, branches):
        self.branches, self.calls = branches, 0

    async def run(self, *args):
        assert all(branch.finished for branch in self.branches)
        self.calls += 1
        return AgentSuccess(RecommendationResult(()))


@pytest.mark.asyncio
async def test_real_graph_overlaps_experts_and_joins_once():
    started, ready = set(), asyncio.Event()
    branches = [
        Branch(kind, started, ready) for kind in ("trends", "style", "nutrition")
    ]
    synthesis = Synthesis(branches)
    roles = WorkflowRoles(Profile(), Retrieval(), *branches, synthesis)
    graph = build_graph(roles, checkpointer=InMemorySaver())
    result = await graph.ainvoke(
        {"request": {"message": "rice"}, "run_id": str(uuid4()), "messages": []},
        {"configurable": {"thread_id": str(uuid4())}},
    )
    assert synthesis.calls == 1
    assert result["final"]["status"] == "success"
    assert started == {"trends", "style", "nutrition"}
    assert (
        len(set(graph.get_graph().nodes) - {"__start__", "__end__", "reset_turn"}) == 6
    )


class ClarifyingProfile:
    def __init__(self):
        self.calls = 0
        self.priors = []

    async def run(self, request, prior=None, **kwargs):
        self.calls += 1
        self.priors.append(prior)
        return AgentSuccess(
            ProfileResult(
                (Category.RECIPE,),
                Preferences(location="California"),
                "Which dish?" if self.calls == 2 else None,
            )
        )


@pytest.mark.asyncio
async def test_next_turn_clears_transient_results_but_retains_profile_and_history():
    started, ready = set(), asyncio.Event()
    branches = [
        Branch(kind, started, ready) for kind in ("trends", "style", "nutrition")
    ]
    profile = ClarifyingProfile()
    graph = build_graph(
        WorkflowRoles(profile, Retrieval(), *branches, Synthesis(branches)),
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": str(uuid4())}}
    first = await graph.ainvoke(
        {"request": {"message": "rice"}, "run_id": str(uuid4())}, config
    )
    assert first["final"]
    second = await graph.ainvoke(
        {"request": {"message": "which one"}, "run_id": str(uuid4())}, config
    )
    assert second["final"] is None
    assert second["retrieval"] is None
    assert second["catalog"] == []
    assert all(second[key] is None for key in ("trend", "style", "nutrition"))
    assert profile.priors[1].preferences.location == "California"
    assert "rice" in second["messages"]
