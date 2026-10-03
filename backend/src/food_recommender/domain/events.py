"""Application activity events; no private reasoning or transport behavior."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from food_recommender.domain.experts import FailureCode
from food_recommender.domain.recommendations import RecommendationResult
from food_recommender.domain.values import AgentRole, nonempty


@dataclass(frozen=True)
class ProgressEvent:
    conversation_id: UUID
    run_id: UUID
    agent: AgentRole
    activity: Literal["started", "completed", "unavailable", "failed"]
    event: Literal["progress"] = field(default="progress", kw_only=True)


@dataclass(frozen=True)
class ClarificationEvent:
    conversation_id: UUID
    run_id: UUID
    question: str
    event: Literal["clarification"] = field(default="clarification", kw_only=True)

    def __post_init__(self) -> None:
        nonempty(self.question)


@dataclass(frozen=True)
class RecommendationsEvent:
    conversation_id: UUID
    run_id: UUID
    result: RecommendationResult
    event: Literal["recommendations"] = field(default="recommendations", kw_only=True)


@dataclass(frozen=True)
class ErrorEvent:
    conversation_id: UUID
    run_id: UUID
    code: FailureCode
    retryable: bool
    event: Literal["error"] = field(default="error", kw_only=True)


@dataclass(frozen=True)
class DoneEvent:
    conversation_id: UUID
    run_id: UUID
    outcome: Literal["completed", "clarification", "failed", "cancelled"]
    event: Literal["done"] = field(default="done", kw_only=True)


type ProgressEvents = (
    ProgressEvent | ClarificationEvent | RecommendationsEvent | ErrorEvent | DoneEvent
)
