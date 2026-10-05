"""Owned history snapshots and conversation persistence contracts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from food_recommender.domain.preferences import Preferences


@dataclass(frozen=True)
class ConversationSnapshot:
    id: UUID
    session_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class MessageSnapshot:
    id: UUID
    role: str
    content: str | None
    payload: dict[str, object] | None
    run_id: UUID | None
    created_at: datetime


class ConversationRepository(Protocol):
    async def delete(
        self, session_id: UUID, conversation_id: UUID
    ) -> tuple[str, ...]: ...

    async def create_session(self, session_id: UUID, token_hash: str) -> None: ...
    async def resolve_session(self, token_hash: str) -> UUID | None: ...
    async def create(
        self, session_id: UUID, conversation_id: UUID
    ) -> ConversationSnapshot: ...
    async def get(
        self, session_id: UUID, conversation_id: UUID
    ) -> ConversationSnapshot: ...
    async def get_profile(
        self, session_id: UUID, conversation_id: UUID
    ) -> Preferences | None: ...
    async def save_profile(
        self, session_id: UUID, conversation_id: UUID, preferences: Preferences
    ) -> None: ...
    async def messages(
        self, session_id: UUID, conversation_id: UUID
    ) -> tuple[MessageSnapshot, ...]: ...
    async def append_message(
        self,
        session_id: UUID,
        conversation_id: UUID,
        message_id: UUID,
        role: str,
        content: str | None,
        *,
        payload: dict[str, object] | None = None,
        run_id: UUID | None = None,
    ) -> None: ...
    async def link_media(
        self, session_id: UUID, conversation_id: UUID, media_id: str
    ) -> None: ...


class RunLease(Protocol):
    async def __aenter__(self) -> None: ...
    async def __aexit__(self, *args: Any) -> bool | None: ...


class ConversationRuns(Protocol):
    def lease(
        self,
        conversation_id: UUID,
        session_id: UUID,
        *,
        protect_context: bool = True,
    ) -> RunLease: ...
