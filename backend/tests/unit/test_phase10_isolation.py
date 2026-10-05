"""Two concurrent owned conversations share providers without sharing constraints."""

import asyncio
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from scripts.phase10_acceptance import (
    FixtureInference,
    FixtureTools,
    OwnedLeases,
    fixture_runner,
    load_labels,
)

from food_recommender.application.errors import ApplicationError
from food_recommender.application.recommendations.workflow import TurnRequest


@pytest.mark.asyncio
async def test_concurrent_threads_and_runner_restart_preserve_only_their_own_context():
    owner_a, owner_b, thread_a, thread_b = (uuid4() for _ in range(4))
    saver = InMemorySaver()
    leases = OwnedLeases({thread_a: owner_a, thread_b: owner_b})
    inference, tools = FixtureInference(), FixtureTools(load_labels()["cases"][3])
    runner = fixture_runner(inference, tools, leases, saver=saver)
    request_a = TurnRequest(
        message="milk allergy",
        categories=["recipe"],
        explicit={
            "constraints": [
                {
                    "kind": "allergen",
                    "value": "milk",
                    "strength": "hard",
                    "origin": "explicit",
                }
            ]
        },
    )
    request_b = TurnRequest(message="pizza please", categories=["recipe"])
    a, b = await asyncio.gather(
        runner.run(owner_a, thread_a, request_a),
        runner.run(owner_b, thread_b, request_b),
    )
    assert a["final"]["result"]["recommendations"] == []
    assert len(b["final"]["result"]["recommendations"]) == 1
    assert a["run_id"] != b["run_id"]
    assert not runner.active and not leases.active
    for owner, thread in [(owner_b, thread_a), (owner_a, thread_b)]:
        with pytest.raises(ApplicationError):
            await runner.read(owner, thread)
    restarted = fixture_runner(inference, tools, leases, saver=saver)
    follow = await restarted.run(owner_a, thread_a, TurnRequest(message="now Italian"))
    assert (
        follow["profile"]["preferences"]["constraints"]
        == a["profile"]["preferences"]["constraints"]
    )
    assert follow["final"]["result"]["recommendations"] == []
    assert (await restarted.read(owner_b, thread_b))["profile"]["preferences"][
        "constraints"
    ] == []


@pytest.mark.asyncio
async def test_provider_deadline_and_cancellation_include_semaphore_queue():
    from food_recommender.application.recommendations.inference import InferenceError
    from food_recommender.application.recommendations.reliability import (
        BudgetedInference,
        RunLimits,
    )

    class Provider:
        calls = 0

        async def generate(self, messages, schema, *, image=None):
            self.calls += 1
            return "{}"

    underlying = Provider()
    semaphore = asyncio.Semaphore(1)
    await semaphore.acquire()
    provider = BudgetedInference(
        underlying,
        limits=RunLimits(call_seconds=0.02, run_seconds=0.1),
        semaphore=semaphore,
    )
    with pytest.raises(InferenceError):
        await provider.generate([], {})
    assert underlying.calls == 0
    pending = asyncio.create_task(provider.generate([], {}))
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    semaphore.release()
    assert await provider.generate([], {}) == "{}"
    assert underlying.calls == 1
