"""Request-scoped activity observer; emits status, never private reasoning."""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Literal

from food_recommender.domain.values import AgentRole

type Activity = Literal["started", "completed", "unavailable", "failed"]
type Progress = Callable[[AgentRole, Activity], Awaitable[None]]
observer: ContextVar[Progress | None] = ContextVar("activity_observer", default=None)
