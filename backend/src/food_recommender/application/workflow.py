"""Validated turn inputs, scoped context and provider-neutral graph dependencies."""

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import Category, ConstraintKind


class ConstraintKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ConstraintKind
    value: str = Field(min_length=1, max_length=100)


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cuisines: tuple[str, ...] | None = None
    flavors: tuple[str, ...] | None = None
    location: str | None = None
    price_band: int | None = Field(default=None, ge=1, le=4)
    constraints: tuple[Constraint, ...] = Field(default=(), max_length=20)
    remove_constraints: tuple[ConstraintKey, ...] = Field(default=(), max_length=20)


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    message: str = Field(min_length=1, max_length=2000)
    explicit: PreferenceUpdate = Field(default_factory=PreferenceUpdate)
    categories: tuple[Category, ...] | None = Field(
        default=None, min_length=1, max_length=2
    )
    media_id: str | None = Field(
        default=None, min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$"
    )
    demo_profile_id: str | None = Field(default=None, min_length=1, max_length=200)


class ToolGateway(Protocol):
    async def call(self, name: str, arguments: dict[str, Any]) -> Any: ...


class RunLease(Protocol):
    async def __aenter__(self) -> None: ...
    async def __aexit__(self, *args: Any) -> bool | None: ...


class ConversationRuns(Protocol):
    def lease(self, conversation_id: UUID, session_id: UUID) -> RunLease: ...


class ToolTransportError(Exception):
    def __init__(self, *, retryable: bool = False, retry_after: float = 0) -> None:
        super().__init__("Tool transport unavailable")
        self.retryable, self.retry_after = retryable, retry_after
