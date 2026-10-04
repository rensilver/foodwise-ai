import asyncio

import pytest

from food_recommender.application.inference import InferenceError
from food_recommender.application.reliability import (
    BudgetedInference,
    RunBudget,
    RunLimits,
    current_budget,
)


class Flaky:
    def __init__(self):
        self.calls = 0

    async def generate(self, messages, schema, *, image=None):
        self.calls += 1
        if self.calls < 3:
            raise InferenceError(retryable=True, retry_after=0.01)
        return "{}"


@pytest.mark.asyncio
async def test_transient_retries_are_bounded_and_recorded():
    waits = []

    async def sleep(delay):
        waits.append(delay)

    underlying = Flaky()
    provider = BudgetedInference(underlying, sleep=sleep, jitter=lambda: 0)
    budget = RunBudget(RunLimits())
    token = current_budget.set(budget)
    try:
        assert await provider.generate([], {}) == "{}"
    finally:
        current_budget.reset(token)
    assert underlying.calls == budget.openai_calls == 3
    assert waits == [0.25, 0.5]


@pytest.mark.asyncio
async def test_provider_concurrency_is_process_bounded():
    active = peak = 0

    class Slow:
        async def generate(self, messages, schema, *, image=None):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return "{}"

    provider = BudgetedInference(Slow(), semaphore=asyncio.Semaphore(3))
    await asyncio.gather(*(provider.generate([], {}) for _ in range(10)))
    assert peak == 3


@pytest.mark.asyncio
async def test_call_deadline_is_not_retried_forever():
    class Slow:
        async def generate(self, messages, schema, *, image=None):
            await asyncio.sleep(10)

    provider = BudgetedInference(
        Slow(), limits=RunLimits(call_seconds=0.02, run_seconds=0.05)
    )
    with pytest.raises(InferenceError):
        await provider.generate([], {})
