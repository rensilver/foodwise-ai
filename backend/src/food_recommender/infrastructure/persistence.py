"""Async PostgreSQL repositories and explicit-commit, rollback-by-default UoW."""

import json
from dataclasses import asdict, fields
from datetime import datetime
from types import TracebackType
from typing import Any, cast
from uuid import UUID

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg import Error as PsycopgError
from psycopg.rows import DictRow
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from food_recommender.application.contracts import preferences_adapter
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.ports import (
    CachedTrends,
    CatalogRepository,
    ConversationRepository,
    ConversationSnapshot,
    MediaCleanupRepository,
    MessageSnapshot,
    TrendItem,
    TrendRepository,
)
from food_recommender.domain.catalog import (
    CatalogSnapshot,
    PreparedCatalog,
    RecipeData,
    RestaurantData,
)
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.catalog import Recipe, Restaurant
from food_recommender.infrastructure.cleanup import MediaCleanupJob
from food_recommender.infrastructure.context import (
    BrowserSession,
    Conversation,
    ConversationMedia,
    Message,
    Profile,
    TrendCache,
    TrendEvidence,
)
from food_recommender.infrastructure.embeddings import ImageEmbedding, TextEmbedding
from food_recommender.infrastructure.provenance import (
    Document,
    Media,
    Source,
    SourceRecord,
)


def create_database_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("Persistence requires PostgreSQL with psycopg")
    return create_async_engine(
        url.set(drivername="postgresql+psycopg"),
        hide_parameters=True,
        pool_pre_ping=True,
    )


def invalid() -> ApplicationError:
    return ApplicationError(ErrorCode.INVALID_REQUEST)


def model_for(ref: EntityRef) -> type[Restaurant] | type[Recipe]:
    if ref.category == Category.RESTAURANT:
        return Restaurant
    if ref.category == Category.RECIPE:
        return Recipe
    raise invalid()


def snapshot(row: Restaurant | Recipe) -> CatalogSnapshot:
    data_type = RestaurantData if isinstance(row, Restaurant) else RecipeData
    values = {field.name: getattr(row, field.name) for field in fields(data_type)}
    for key in ("ingredients", "directions", "signatures", "shortcomings", "allergens"):
        if values.get(key) is not None:
            values[key] = tuple(values[key])
    return CatalogSnapshot(data_type(**values), row.version)


class PostgresCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, ref: EntityRef) -> CatalogSnapshot:
        row = await self.session.get(model_for(ref), ref.id, populate_existing=True)
        if row is None:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        return snapshot(cast(Restaurant | Recipe, row))

    async def create(self, prepared: PreparedCatalog) -> CatalogSnapshot:
        model = Restaurant if isinstance(prepared.data, RestaurantData) else Recipe
        await self.session.execute(insert(model).values(**asdict(prepared.data)))
        await self._write_content(prepared)
        ref = EntityRef(
            Category.RESTAURANT if model is Restaurant else Category.RECIPE,
            prepared.data.id,
        )
        return await self.get(ref)

    def _validate(
        self,
        ref: EntityRef,
        expected_version: int,
        prepared: PreparedCatalog | None = None,
    ) -> None:
        if type(expected_version) is not int or expected_version < 1:
            raise invalid()
        if prepared is not None and (
            ref.id != prepared.data.id
            or (ref.category == Category.RESTAURANT)
            != isinstance(prepared.data, RestaurantData)
        ):
            raise invalid()

    async def _remove_content(self, ref: EntityRef) -> tuple[str, ...]:
        link = (
            SourceRecord.restaurant_id
            if ref.category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        record_ids = select(SourceRecord.id).where(link == ref.id)
        await self.session.execute(
            delete(Document).where(Document.source_record_id.in_(record_ids))
        )
        keys = tuple(
            (
                await self.session.execute(
                    delete(Media)
                    .where(Media.source_record_id.in_(record_ids))
                    .returning(Media.storage_key)
                )
            ).scalars()
        )
        for key in keys:
            await self.session.execute(
                upsert(MediaCleanupJob).values(storage_key=key).on_conflict_do_nothing()
            )
        return keys

    async def replace(
        self, ref: EntityRef, prepared: PreparedCatalog, expected_version: int
    ) -> CatalogSnapshot:
        self._validate(ref, expected_version, prepared)
        current = await self.get(ref)
        if (current.data.source_id, current.data.source_record_id) != (
            prepared.data.source_id,
            prepared.data.source_record_id,
        ):
            raise invalid()
        model = model_for(ref)
        values = asdict(prepared.data)
        for key in ("id", "source_id", "source_record_id"):
            values.pop(key)
        changed = await self.session.scalar(
            update(model)
            .where(model.id == ref.id, model.version == expected_version)
            .values(**values, version=model.version + 1)
            .returning(model.id)
        )
        if changed is None:
            raise ApplicationError(ErrorCode.CONFLICT)
        # Remove old retrieval rows; source/raw revisions survive as provenance.
        await self._remove_content(ref)
        await self._write_content(prepared)
        return await self.get(ref)

    async def delete(self, ref: EntityRef, expected_version: int) -> tuple[str, ...]:
        self._validate(ref, expected_version)
        model = model_for(ref)
        # Lock by updating the version before removing linked retrieval content.
        changed = await self.session.scalar(
            update(model)
            .where(model.id == ref.id, model.version == expected_version)
            .values(version=model.version + 1)
            .returning(model.id)
        )
        if changed is None:
            await self.get(ref)
            raise ApplicationError(ErrorCode.CONFLICT)
        keys = await self._remove_content(ref)
        link = (
            SourceRecord.restaurant_id
            if ref.category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        await self.session.execute(
            update(SourceRecord).where(link == ref.id).values({link.key: None})
        )
        await self.session.execute(delete(model).where(model.id == ref.id))
        return keys

    async def _ensure(
        self, model: type[Source] | type[SourceRecord], payload: dict[str, Any]
    ) -> None:
        # Reusing an immutable provenance ID requires exactly the same values.
        existing = await self.session.get(model, payload["id"])
        if existing is None:
            await self.session.execute(insert(model).values(**payload))
        elif any(getattr(existing, key) != value for key, value in payload.items()):
            raise ApplicationError(ErrorCode.CONFLICT)

    async def _write_content(self, prepared: PreparedCatalog) -> None:
        for source in prepared.sources:
            await self._ensure(Source, asdict(source))
        category = (
            "restaurant" if isinstance(prepared.data, RestaurantData) else "recipe"
        )
        for record in prepared.records:
            await self._ensure(
                SourceRecord, {**asdict(record), f"{category}_id": prepared.data.id}
            )
        for media in prepared.media:
            await self.session.execute(insert(Media).values(**asdict(media)))
        for document in prepared.documents:
            await self.session.execute(insert(Document).values(**asdict(document)))
        for vectors, model, parent in (
            (prepared.text_embeddings, TextEmbedding, "document_id"),
            (prepared.image_embeddings, ImageEmbedding, "media_id"),
        ):
            for vector in vectors:
                await self.session.execute(
                    insert(model).values(
                        id=vector.id,
                        **{parent: vector.parent_id},
                        model=vector.model,
                        revision=vector.revision,
                        input_hash=vector.input_hash,
                        dimension=len(vector.values),
                        embedding=list(vector.values),
                    )
                )


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


class PostgresTrendRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, query_hash: str, now: datetime) -> CachedTrends | None:
        if now.tzinfo is None:
            raise invalid()
        row = await self.session.scalar(
            select(TrendCache).where(
                TrendCache.query_hash == query_hash,
                TrendCache.retrieved_at <= now,
                TrendCache.expires_at > now,
            )
        )
        if row is None:
            return None
        evidence = (
            await self.session.scalars(
                select(TrendEvidence)
                .where(TrendEvidence.query_hash == query_hash)
                .order_by(TrendEvidence.position)
            )
        ).all()
        return CachedTrends(
            row.query_hash,
            row.query,
            row.retrieved_at,
            row.expires_at,
            tuple(
                TrendItem(
                    item.id,
                    item.url,
                    item.excerpt,
                    item.published_on,
                    item.retrieved_at,
                )
                for item in evidence
            ),
        )

    async def put(self, result: CachedTrends) -> None:
        if len(result.evidence) > 5:
            raise invalid()
        statement = upsert(TrendCache).values(
            query_hash=result.query_hash,
            query=result.query,
            retrieved_at=result.retrieved_at,
            expires_at=result.expires_at,
        )
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[TrendCache.query_hash],
                set_={
                    "query": statement.excluded.query,
                    "retrieved_at": statement.excluded.retrieved_at,
                    "expires_at": statement.excluded.expires_at,
                },
            )
        )
        await self.session.execute(
            delete(TrendEvidence).where(TrendEvidence.query_hash == result.query_hash)
        )
        for position, item in enumerate(result.evidence):
            await self.session.execute(
                insert(TrendEvidence).values(
                    id=item.id,
                    query_hash=result.query_hash,
                    position=position,
                    url=item.url,
                    excerpt=item.excerpt,
                    published_on=item.published_on,
                    retrieved_at=item.retrieved_at,
                )
            )


class PostgresMediaCleanupRepository:
    async def has_pending(self, keys: tuple[str, ...]) -> bool:
        return (
            await self.session.scalar(
                select(MediaCleanupJob.storage_key)
                .where(MediaCleanupJob.storage_key.in_(keys))
                .limit(1)
            )
            is not None
        )

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def pending(
        self, *, limit: int, keys: tuple[str, ...] | None = None
    ) -> tuple[str, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise invalid()
        statement = (
            select(MediaCleanupJob.storage_key)
            .order_by(MediaCleanupJob.created_at, MediaCleanupJob.storage_key)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if keys is not None:
            statement = statement.where(MediaCleanupJob.storage_key.in_(keys))
        return tuple((await self.session.scalars(statement)).all())

    async def referenced(self, storage_key: str) -> bool:
        return (
            await self.session.scalar(
                select(Media.id).where(Media.storage_key == storage_key).limit(1)
            )
            is not None
        )

    async def complete(self, storage_key: str) -> None:
        await self.session.execute(
            delete(MediaCleanupJob).where(MediaCleanupJob.storage_key == storage_key)
        )


class PostgresUnitOfWork:
    catalog: CatalogRepository
    conversations: ConversationRepository
    trends: TrendRepository
    cleanup: MediaCleanupRepository

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "PostgresUnitOfWork":
        if self.session is not None:
            raise RuntimeError("Unit of work cannot be reentered")
        self.session = self.sessions()
        await self.session.begin()
        self.catalog = PostgresCatalogRepository(self.session)
        self.conversations = PostgresConversationRepository(self.session)
        self.trends = PostgresTrendRepository(self.session)
        self.cleanup = PostgresMediaCleanupRepository(self.session)
        return self

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has not been entered")
        await self.session.commit()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.session is not None:
            try:
                await self.session.rollback()
            finally:
                await self.session.close()
                self.session = None
        if isinstance(exc, IntegrityError):
            code = (
                ErrorCode.CONFLICT
                if getattr(exc.orig, "sqlstate", None) == "23505"
                else ErrorCode.INVALID_REQUEST
            )
            raise ApplicationError(code) from exc
        if isinstance(exc, (SQLAlchemyError, PsycopgError)):
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from exc
