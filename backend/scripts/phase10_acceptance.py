"""Offline, source-backed execution of the real six roles with fake boundaries.

This is an acceptance harness, not a retrieval or paid-provider quality benchmark.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver

from food_recommender.agents.graph import WorkflowRoles, build_graph
from food_recommender.agents.nodes.nutrition import NutritionExpert
from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.agents.nodes.rag import RAGRetriever
from food_recommender.agents.nodes.recommendation import RecommendationExpert
from food_recommender.agents.nodes.style import FoodStyleExpert
from food_recommender.agents.nodes.trend import FoodTrendAnalyst
from food_recommender.agents.runner import GraphRunner
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.recommendations.reliability import (
    BudgetedInference,
    BudgetedTools,
)
from food_recommender.application.recommendations.workflow import TurnRequest
from food_recommender.application.trends.service import TrendResult
from food_recommender.domain.evidence import CandidateEvidence, Citation, CitationKind
from food_recommender.domain.values import Category, EntityRef
from food_recommender.retrieval.late_fusion import FusedCandidate
from food_recommender.retrieval.multimodal import MultimodalOutcome

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "evaluation/phase10/acceptance.json"


def load_labels():
    return json.loads(LABELS.read_text())


def source_candidate(category, identity):
    filename = (
        "data/Recipes.json"
        if category == "recipe"
        else "data/structured_restaurant_data.json"
    )
    key = "id" if category == "recipe" else "itemId"
    record = next(
        row
        for row in json.loads((ROOT / filename).read_text())
        if str(row[key]) == identity
    )
    ref = EntityRef(Category(category), identity)
    citation = Citation(
        f"{category}:{identity}:catalog",
        CitationKind.CATALOG,
        filename,
        record["name"],
        ref,
        identity,
        f"{category}:{identity}:name",
    )
    return FusedCandidate(
        CandidateEvidence(ref, (citation,), 1),
        record["name"],
        tuple(record["ingredients"]) if category == "recipe" else None,
        None,
        1,
        1,
        1,
        None,
        (),
    )


class FixtureInference:
    def __init__(self):
        self.patch = {}
        self.calls = []

    async def generate(self, messages, schema, *, image=None):
        context = json.loads(messages[1]["content"])
        self.calls.append(context)
        if "request" in context:
            return json.dumps(self.patch)
        if "attempt" in context:
            return json.dumps({"query": context["message"]})
        if "deterministic_assessments" in context:
            return json.dumps({"assessments": context["deterministic_assessments"]})
        if "eligible_candidates" in context:
            return json.dumps(
                {
                    "recommendations": [
                        {
                            "entity": c["evidence"]["entity"],
                            "explanation": c["evidence"]["citations"][0]["excerpt"],
                            "citation_ids": [c["evidence"]["citations"][0]["id"]],
                        }
                        for c in context["eligible_candidates"][:5]
                    ]
                }
            )
        if "candidates" in context:
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
        raise AssertionError("Unexpected fixture inference request")


class FixtureTools:
    def __init__(self, case):
        self.case, self.calls = case, []

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search_food_trends":
            return TrendResult(status="unavailable", reason="missing_credentials")
        assert name in {"search_restaurants", "search_recipes", "search_images"}
        category = (
            "restaurant"
            if name == "search_restaurants"
            else arguments["request"].get("category", "recipe")
        )
        candidates = tuple(
            source_candidate(category, identity)
            for identity in self.case["candidate_ids"].get(category, [])
        )
        # Image fixture exercises routing only; actual CLIP identity is measured separately.
        return MultimodalOutcome(
            "success" if candidates else "no_results", candidates, (), 0
        )


class OwnedLeases:
    def __init__(self, owners):
        self.owners = owners
        self.active = set()

    @asynccontextmanager
    async def lease(self, conversation_id, session_id, *, protect_context=True):
        if self.owners.get(conversation_id) != session_id:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        if conversation_id in self.active:
            raise ApplicationError(ErrorCode.CONFLICT)
        self.active.add(conversation_id)
        try:
            yield
        finally:
            self.active.remove(conversation_id)


def fixture_runner(inference, tools, leases, *, saver=None):
    provider, gateway = BudgetedInference(inference), BudgetedTools(tools)
    roles = WorkflowRoles(
        UserProfileGenerator(provider),
        RAGRetriever(provider, gateway),
        FoodTrendAnalyst(provider, gateway),
        FoodStyleExpert(provider),
        NutritionExpert(provider),
        RecommendationExpert(provider),
    )
    return GraphRunner(
        build_graph(roles, checkpointer=saver or InMemorySaver()), leases
    )


async def execute_case(case):
    owner, conversation = uuid4(), uuid4()
    inference, tools = FixtureInference(), FixtureTools(case)
    runner = fixture_runner(inference, tools, OwnedLeases({conversation: owner}))
    states = []
    for turn in case["turns"]:
        inference.patch = turn["profile_patch"]
        states.append(
            await runner.run(
                owner, conversation, TurnRequest.model_validate(turn["request"])
            )
        )
    return states, inference, tools


def audit_state(state):
    """Independent acceptance gate over published references and canonical restrictions."""
    from food_recommender.agents.graph import catalog, profile
    from food_recommender.application.recommendations.nutrition_rules import (
        deterministic_nutrition,
    )
    from food_recommender.domain.values import EvidenceState, Strength

    candidates = catalog(state)
    preferences = profile(state)
    known = {c.evidence.entity: c for c in candidates}
    authoritative = {
        a.entity: a.state
        for a in deterministic_nutrition(preferences, candidates).assessments
    }
    hard = any(c.strength == Strength.HARD for c in preferences.preferences.constraints)
    violations = dict.fromkeys(
        (
            "fabricated_recommendations",
            "fabricated_citations",
            "hard_constraint_violations",
            "duplicate_recommendations",
        ),
        0,
    )
    seen = set()
    for item in (state.get("final") or {}).get("result", {}).get("recommendations", []):
        ref = EntityRef(Category(item["entity"]["category"]), item["entity"]["id"])
        violations["duplicate_recommendations"] += ref in seen
        seen.add(ref)
        food = known.get(ref)
        if food is None:
            violations["fabricated_recommendations"] += 1
            continue
        allowed = {citation.id for citation in food.evidence.citations}
        violations["fabricated_citations"] += len(set(item["citation_ids"]) - allowed)
        violations["hard_constraint_violations"] += authoritative[
            ref
        ] == EvidenceState.CONFLICTING or (
            hard and authoritative[ref] != EvidenceState.SUPPORTED
        )
    return violations


if __name__ == "__main__":

    async def main():
        for case in load_labels()["cases"]:
            states, _, _ = await execute_case(case)
            print(case["id"], [s["final"]["status"] for s in states])

    asyncio.run(main())
