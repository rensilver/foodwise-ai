"""Versioned scenarios run every real role and control node offline."""

import pytest
from scripts.phase10_acceptance import execute_case, load_labels


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_labels()["cases"], ids=lambda case: case["id"])
async def test_versioned_outcomes(case):
    states, inference, tools = await execute_case(case)
    for turn, state in zip(case["turns"], states, strict=True):
        if turn["expected"] == "clarification":
            assert state["profile"]["clarification"]
            assert state["catalog"] == []
            assert not tools.calls
            continue
        assert state["final"]["status"] == "success"
        items = state["final"]["result"]["recommendations"]
        assert bool(items) == (turn["expected"] == "recommendations")
    if "image_recipe_id" in case:
        assert any(name == "search_images" for name, _ in tools.calls)
    if "follow-up" in case.get("tags", []):
        assert (
            states[1]["profile"]["preferences"]["constraints"]
            == states[0]["profile"]["preferences"]["constraints"]
        )
        assert states[2]["profile"]["preferences"]["constraints"] == []
        assert len({state["run_id"] for state in states}) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_labels()["cases"], ids=lambda case: case["id"])
async def test_zero_grounding_and_constraint_violations(case):
    from scripts.phase10_acceptance import audit_state

    states, _, _ = await execute_case(case)
    for state in states:
        assert audit_state(state) == {
            "fabricated_recommendations": 0,
            "fabricated_citations": 0,
            "hard_constraint_violations": 0,
            "duplicate_recommendations": 0,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "attack", ["unknown-entity", "unknown-citation", "cross-category"]
)
async def test_forged_provider_references_fail_before_publishing(attack):
    import json
    from uuid import uuid4

    from scripts.phase10_acceptance import (
        FixtureInference,
        FixtureTools,
        OwnedLeases,
        fixture_runner,
    )

    from food_recommender.application.recommendations.workflow import TurnRequest

    class ForgingInference(FixtureInference):
        async def generate(self, messages, schema, *, image=None):
            payload = await super().generate(messages, schema, image=image)
            context = json.loads(messages[1]["content"])
            if "eligible_candidates" in context:
                response = json.loads(payload)
                item = response["recommendations"][0]
                if attack == "unknown-entity":
                    item["entity"]["id"] = "fabricated"
                elif attack == "unknown-citation":
                    item["citation_ids"] = ["fabricated"]
                else:
                    item["entity"]["category"] = "restaurant"
                return json.dumps(response)
            return payload

    owner, conversation = uuid4(), uuid4()
    inference = ForgingInference()
    case = load_labels()["cases"][0]
    runner = fixture_runner(
        inference, FixtureTools(case), OwnedLeases({conversation: owner})
    )
    state = await runner.run(
        owner, conversation, TurnRequest.model_validate(case["turns"][0]["request"])
    )
    assert state["final"]["status"] == "failure"
    assert state["final"]["code"] == "validation_failed"
    assert sum("eligible_candidates" in call for call in inference.calls) == 2
