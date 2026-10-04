"""Shared per-turn deadlines and usage; process-wide inference concurrency is injected."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from food_recommender.application.inference import Inference, InferenceError
from food_recommender.application.workflow import ToolGateway, ToolTransportError
from food_recommender.domain.experts import AgentFailure


@dataclass(frozen=True)
class RunLimits:
    call_seconds: float = 30
    run_seconds: float = 120
    transport_retries: int = 2
    schema_repairs: int = 2
    openai_concurrency: int = 3

    def __post_init__(self) -> None:
        if not (
            0 < self.call_seconds <= self.run_seconds <= 120
            and 0 <= self.transport_retries <= 2
            and 0 <= self.schema_repairs <= 2
            and 1 <= self.openai_concurrency <= 3
        ):
            raise ValueError("Unsupported run limits")


class RunExhausted(InferenceError):
    """Safe deadline marker; all repairs/retries use the same run clock."""


@dataclass
class RunBudget:
    limits: RunLimits
    clock: Callable[[], float] = time.monotonic
    started: float = field(init=False)
    openai_calls: int = 0
    tool_calls: int = 0
    search_calls: int = 0
    token_usage: int = 0
    retrieval_attempts: int = 0
    stages: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.started = self.clock()

    def remaining(self) -> float:
        remaining = self.limits.run_seconds - (self.clock() - self.started)
        if remaining <= 0:
            raise RunExhausted()
        return remaining

    def summary(self) -> dict[str, Any]:
        return {
            "duration_ms": (self.clock() - self.started) * 1000,
            "openai_calls": self.openai_calls,
            "tool_calls": self.tool_calls,
            "search_calls": self.search_calls,
            "token_usage": self.token_usage,
            "retrieval_attempts": self.retrieval_attempts,
            "stages": list(self.stages),
        }


current_budget: ContextVar[RunBudget | None] = ContextVar(
    "foodwise_run_budget", default=None
)


class BudgetedInference:
    def __init__(
        self,
        inference: Inference,
        *,
        limits: RunLimits = RunLimits(),
        semaphore: asyncio.Semaphore | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: random.uniform(0, 0.2),
    ) -> None:
        self.inference, self.limits = inference, limits
        self.semaphore = (
            semaphore
            if semaphore is not None
            else asyncio.Semaphore(limits.openai_concurrency)
        )
        self.sleep, self.jitter = sleep, jitter

    async def generate(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        image: str | None = None,
    ) -> str:
        budget = current_budget.get()
        seconds = (
            min(self.limits.call_seconds, budget.remaining())
            if budget
            else self.limits.call_seconds
        )
        try:
            async with asyncio.timeout(seconds):
                for attempt in range(self.limits.transport_retries + 1):
                    if budget:
                        budget.remaining()
                    try:
                        async with self.semaphore:
                            if budget:
                                budget.openai_calls += 1
                            return await self.inference.generate(
                                messages, schema, image=image
                            )
                    except InferenceError as error:
                        if (
                            not error.retryable
                            or attempt == self.limits.transport_retries
                        ):
                            raise
                        delay = (
                            max(error.retry_after, 0.25 * 2**attempt) + self.jitter()
                        )
                        if budget and delay >= budget.remaining():
                            raise RunExhausted() from None
                        await self.sleep(delay)
        except TimeoutError:
            if budget and budget.clock() - budget.started >= budget.limits.run_seconds:
                raise RunExhausted() from None
            raise InferenceError() from None
        raise InferenceError()


class BudgetedTools:
    def __init__(self, tools: ToolGateway, *, limits: RunLimits = RunLimits()) -> None:
        self.tools, self.limits = tools, limits

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        budget = current_budget.get()
        seconds = (
            min(self.limits.call_seconds, budget.remaining())
            if budget
            else self.limits.call_seconds
        )
        async with asyncio.timeout(seconds):
            for attempt in range(self.limits.transport_retries + 1):
                if budget:
                    budget.remaining()
                    budget.tool_calls += 1
                try:
                    result = await self.tools.call(name, arguments)
                    if budget and name == "search_food_trends":
                        budget.search_calls += getattr(result, "search_calls", 0)
                    return result
                except ToolTransportError as error:
                    if not error.retryable or attempt == self.limits.transport_retries:
                        raise
                    delay = max(error.retry_after, 0.25 * 2**attempt) + random.uniform(
                        0, 0.2
                    )
                    if budget and delay >= budget.remaining():
                        raise RunExhausted() from None
                    await asyncio.sleep(delay)
        raise ToolTransportError()


def inference_failure(error: Exception) -> AgentFailure:
    if isinstance(error, RunExhausted):
        return AgentFailure("budget_exhausted")
    if isinstance(error, InferenceError) and not error.schema_error:
        return AgentFailure("dependency_unavailable", retryable=error.retryable)
    return AgentFailure("invalid_response")
