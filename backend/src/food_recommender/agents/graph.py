"""Six real LangGraph roles with sequential retrieval and an explicit barrier join."""

import json
from dataclasses import dataclass
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic_core import to_jsonable_python

from food_recommender.agents.nodes.nutrition import NutritionExpert
from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.agents.nodes.rag import RAGRetriever
from food_recommender.agents.nodes.recommendation import RecommendationExpert
from food_recommender.agents.nodes.style import FoodStyleExpert
from food_recommender.agents.nodes.trend import FoodTrendAnalyst
from food_recommender.agents.state import CATALOG_ADAPTER, GraphState
from food_recommender.application.contracts import (
    nutrition_outcome_adapter,
    profile_adapter,
    style_outcome_adapter,
    trend_outcome_adapter,
)
from food_recommender.application.workflow import TurnRequest
from food_recommender.domain.experts import AgentSuccess, AgentUnavailable


@dataclass(frozen=True)
class WorkflowRoles:
    profile: UserProfileGenerator
    retrieval: RAGRetriever
    trend: FoodTrendAnalyst
    style: FoodStyleExpert
    nutrition: NutritionExpert
    recommendation: RecommendationExpert


def wire(value: Any) -> Any:
    return to_jsonable_python(value)


def profile(state: GraphState) -> Any:
    return profile_adapter.validate_json(json.dumps(state["profile"]))


def catalog(state: GraphState) -> Any:
    return CATALOG_ADAPTER.validate_json(json.dumps(state.get("catalog", [])))


def build_graph(
    roles: WorkflowRoles, *, checkpointer: BaseCheckpointSaver[Any] | None = None
) -> CompiledStateGraph[Any, Any, Any, Any]:
    async def generate_profile(state: GraphState) -> dict[str, Any]:
        prior = profile(state) if state.get("profile") else None
        outcome = await roles.profile.run(
            TurnRequest.model_validate(state["request"]),
            prior,
            history=tuple(state.get("messages", [])[-20:]),
        )
        updates = {"profile_outcome": wire(outcome)}
        if isinstance(outcome, AgentSuccess):
            updates["profile"] = wire(outcome.result)
        return updates

    def after_profile(state: GraphState) -> str:
        outcome = state.get("profile_outcome") or {}
        if outcome.get("status") != "success" or (state.get("profile") or {}).get(
            "clarification"
        ):
            return END
        return "retrieval"

    async def retrieve(state: GraphState) -> dict[str, Any]:
        result = await roles.retrieval.run(
            TurnRequest.model_validate(state["request"]), profile(state)
        )
        return {"retrieval": wire(result.outcome), "catalog": wire(result.catalog)}

    def after_retrieval(state: GraphState) -> list[str]:
        return (
            ["trend", "style", "nutrition"]
            if (state.get("retrieval") or {}).get("status") == "success"
            else [END]
        )

    async def trend(state: GraphState) -> dict[str, Any]:
        try:
            outcome = await roles.trend.run(profile(state), catalog(state))
        except Exception:
            outcome = AgentUnavailable("trends_unavailable")
        return {"trend": wire(outcome)}

    async def style(state: GraphState) -> dict[str, Any]:
        try:
            outcome = await roles.style.run(profile(state), catalog(state))
        except Exception:
            outcome = AgentUnavailable("style_unavailable")
        return {"style": wire(outcome)}

    async def nutrition(state: GraphState) -> dict[str, Any]:
        try:
            outcome = await roles.nutrition.run(profile(state), catalog(state))
        except Exception:
            outcome = AgentUnavailable("nutrition_unavailable")
        return {"nutrition": wire(outcome)}

    async def synthesize(state: GraphState) -> dict[str, Any]:
        result = await roles.recommendation.run(
            profile(state),
            catalog(state),
            trend_outcome_adapter.validate_json(json.dumps(state["trend"])),
            style_outcome_adapter.validate_json(json.dumps(state["style"])),
            nutrition_outcome_adapter.validate_json(json.dumps(state["nutrition"])),
        )
        return {"final": wire(result)}

    graph = StateGraph(GraphState)
    for name, node in (
        ("profile", generate_profile),
        ("retrieval", retrieve),
        ("trend", trend),
        ("style", style),
        ("nutrition", nutrition),
        ("recommendation", synthesize),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "profile")
    graph.add_conditional_edges("profile", after_profile)
    graph.add_conditional_edges("retrieval", after_retrieval)
    graph.add_edge(["trend", "style", "nutrition"], "recommendation")
    graph.add_edge("recommendation", END)
    return graph.compile(checkpointer=checkpointer)
