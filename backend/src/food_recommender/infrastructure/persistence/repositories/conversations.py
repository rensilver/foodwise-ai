"""Owned conversation persistence and transactional LangGraph checkpoint erasure."""

import json
from typing import cast
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import DictRow
from sqlalchemy import delete, insert, select, text
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from food_recommender.application.contracts import preferences_adapter
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.ports import ConversationSnapshot, MessageSnapshot
from food_recommender.domain.preferences import Preferences
from food_recommender.infrastructure.persistence.models.cleanup import MediaCleanupJob
from food_recommender.infrastructure.persistence.models.context import (
    BrowserSession,
    Conversation,
    ConversationMedia,
    Message,
    Profile,
)
from food_recommender.infrastructure.persistence.models.provenance import Media


class PostgresConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _owned(
        self, session_id: UUID, conversation_id: UUID, *, lock: bool = False
    ) -> Conversation:
        statement = select(Conversation).where(
            Conversation.id == conversation_id, Conversation.session_id == session_id
        )
        if lock:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        if row is None:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        return row

    async def delete(self, session_id: UUID, conversation_id: UUID) -> tuple[str, ...]:
        await self._owned(session_id, conversation_id, lock=True)
        uploads = (
            await self.session.scalars(
                select(Media)
                .join(ConversationMedia, ConversationMedia.media_id == Media.id)
                .where(
                    ConversationMedia.conversation_id == conversation_id,
                    Media.owner_session_id == session_id,
                )
                .order_by(Media.id)
                .with_for_update(of=Media)
            )
        ).all()
        await self.session.execute(
            delete(Conversation).where(Conversation.id == conversation_id)
        )
        # The supported saver uses the exact same psycopg connection and existing
        # transaction/savepoint. Its thread deletion cannot commit independently.
        connection = await self.session.connection()
        original_path = await self.session.scalar(text("SHOW search_path"))
        await self.session.execute(
            text("SELECT set_config('search_path', 'foodwise_checkpoints', true)")
        )
        raw = await connection.get_raw_connection()
        driver = cast(AsyncConnection[DictRow], raw.driver_connection)
        try:
            await AsyncPostgresSaver(driver).adelete_thread(str(conversation_id))
        finally:
            await self.session.execute(
                text("SELECT set_config('search_path', :path, true)"),
                {"path": original_path},
            )
        keys: list[str] = []
        for upload in uploads:
            shared = await self.session.scalar(
                select(ConversationMedia.media_id)
                .where(ConversationMedia.media_id == upload.id)
                .limit(1)
            )
            if shared is None:
                await self.session.execute(delete(Media).where(Media.id == upload.id))
                await self.session.execute(
                    upsert(MediaCleanupJob)
                    .values(storage_key=upload.storage_key)
                    .on_conflict_do_nothing()
                )
                keys.append(upload.storage_key)
        return tuple(keys)

    async def create_session(self, session_id: UUID, token_hash: str) -> None:
        await self.session.execute(
            insert(BrowserSession).values(id=session_id, token_hash=token_hash)
        )

    async def resolve_session(self, token_hash: str) -> UUID | None:
        return await self.session.scalar(
            select(BrowserSession.id).where(BrowserSession.token_hash == token_hash)
        )

    async def create(
        self, session_id: UUID, conversation_id: UUID
    ) -> ConversationSnapshot:
        await self.session.execute(
            insert(Conversation).values(id=conversation_id, session_id=session_id)
        )
        return await self.get(session_id, conversation_id)

    async def get(
        self, session_id: UUID, conversation_id: UUID
    ) -> ConversationSnapshot:
        row = await self._owned(session_id, conversation_id)
        return ConversationSnapshot(row.id, row.session_id, row.created_at)

    async def get_profile(
        self, session_id: UUID, conversation_id: UUID
    ) -> Preferences | None:
        await self._owned(session_id, conversation_id)
        profile = await self.session.get(Profile, conversation_id)
        return (
            None
            if profile is None
            else preferences_adapter.validate_json(json.dumps(profile.preferences))
        )

    async def save_profile(
        self, session_id: UUID, conversation_id: UUID, preferences: Preferences
    ) -> None:
        await self._owned(session_id, conversation_id, lock=True)
        payload = json.loads(preferences_adapter.dump_json(preferences))
        statement = upsert(Profile).values(
            conversation_id=conversation_id, preferences=payload
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[Profile.conversation_id],
                set_={"preferences": statement.excluded.preferences},
            )
        )

    async def messages(
        self, session_id: UUID, conversation_id: UUID
    ) -> tuple[MessageSnapshot, ...]:
        await self._owned(session_id, conversation_id)
        rows = (
            await self.session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at, Message.id)
            )
        ).all()
        return tuple(
            MessageSnapshot(
                row.id, row.role, row.content, row.payload, row.run_id, row.created_at
            )
            for row in rows
        )

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
    ) -> None:
        await self._owned(session_id, conversation_id, lock=True)
        await self.session.execute(
            insert(Message).values(
                id=message_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                payload=payload,
                run_id=run_id,
            )
        )

    async def link_media(
        self, session_id: UUID, conversation_id: UUID, media_id: str
    ) -> None:
        await self._owned(session_id, conversation_id, lock=True)
        media = await self.session.scalar(
            select(Media)
            .where(Media.id == media_id, Media.owner_session_id == session_id)
            .with_for_update()
        )
        if media is None:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        await self.session.execute(
            upsert(ConversationMedia)
            .values(
                conversation_id=conversation_id,
                session_id=session_id,
                media_id=media_id,
            )
            .on_conflict_do_nothing()
        )
