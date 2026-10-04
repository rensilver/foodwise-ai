"""Narrow persistence boundaries; no SDK/ORM objects cross these ports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from food_recommender.domain.catalog import CatalogSnapshot, PreparedCatalog
from food_recommender.domain.evidence import Citation
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import Category, EntityRef

if TYPE_CHECKING:
    from food_recommender.application.media import MediaRepository


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


@dataclass(frozen=True)
class TrendItem:
    id: UUID
    url: str
    excerpt: str
    published_on: date | None
    retrieved_at: datetime


@dataclass(frozen=True)
class CachedTrends:
    query_hash: str
    query: str
    retrieved_at: datetime
    expires_at: datetime
    evidence: tuple[TrendItem, ...]


class CatalogRepository(Protocol):
    async def browse(
        self, category: Category, filters: dict[str, object]
    ) -> tuple[tuple[CatalogSnapshot, ...], int]: ...
    async def citations(self, ref: EntityRef) -> tuple[Citation, ...]: ...
    async def get(self, ref: EntityRef) -> CatalogSnapshot: ...
    async def create(self, prepared: PreparedCatalog) -> CatalogSnapshot: ...
    async def replace(
        self, ref: EntityRef, prepared: PreparedCatalog, expected_version: int
    ) -> CatalogSnapshot: ...
    async def delete(
        self, ref: EntityRef, expected_version: int
    ) -> tuple[str, ...]: ...


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


class TrendRepository(Protocol):
    async def get(self, query_hash: str, now: datetime) -> CachedTrends | None: ...
    async def put(self, result: CachedTrends) -> None: ...


class MediaFiles(Protocol):
    async def delete(self, storage_key: str) -> None: ...


class MediaCleanupRepository(Protocol):
    async def has_pending(self, keys: tuple[str, ...]) -> bool: ...

    async def pending(
        self, *, limit: int, keys: tuple[str, ...] | None = None
    ) -> tuple[str, ...]: ...
    async def referenced(self, storage_key: str) -> bool: ...
    async def complete(self, storage_key: str) -> None: ...


class UnitOfWork(Protocol):
    media: MediaRepository
    catalog: CatalogRepository
    conversations: ConversationRepository
    trends: TrendRepository
    cleanup: MediaCleanupRepository

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...
