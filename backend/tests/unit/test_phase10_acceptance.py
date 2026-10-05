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
