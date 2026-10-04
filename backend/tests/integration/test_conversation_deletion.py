"""Atomic conversation erasure and retryable private-file cleanup."""

from pathlib import Path
from uuid import uuid4

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from sqlalchemy import insert, select, text
from test_repositories import bundle
from test_repositories import repositories as repositories

from food_recommender.application.catalog import CatalogService
from food_recommender.application.conversations import ConversationService
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.media_cleanup import MediaCleanupService
from food_recommender.domain.preferences import Preferences
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.persistence.checkpoints import (
    checkpoint_saver,
    setup_checkpoints,
)
from food_recommender.infrastructure.persistence.models.catalog import Recipe
from food_recommender.infrastructure.persistence.models.cleanup import MediaCleanupJob
from food_recommender.infrastructure.persistence.models.context import (
    Conversation,
    ConversationMedia,
    Message,
    Profile,
)
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    Media,
    SourceRecord,
)
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


async def seed(factory, media_root):
    owner, stranger, conversation, sibling, other = (uuid4() for _ in range(5))
    async with PostgresUnitOfWork(factory) as uow:
        await uow.conversations.create_session(owner, "a" * 64)
        await uow.conversations.create_session(stranger, "b" * 64)
        for session_id, cid in (
            (owner, conversation),
            (owner, sibling),
            (stranger, other),
        ):
            await uow.conversations.create(session_id, cid)
            await uow.conversations.save_profile(
                session_id, cid, Preferences(location="California")
            )
            await uow.conversations.append_message(
                session_id, cid, uuid4(), "user", "Dinner"
            )
        for mid, session_id in (
            ("private", owner),
            ("shared", owner),
            ("other", stranger),
        ):
            await uow.session.execute(
                insert(Media).values(
                    id=mid,
                    owner_session_id=session_id,
                    storage_key=f"{mid}.png",
                    mime_type="image/png",
                    byte_size=10,
                    width=2,
                    height=2,
                    content_hash="a" * 64,
                    ingestion_version="upload-v1",
                    attribution="source",
                )
            )
            (media_root / f"{mid}.png").write_bytes(b"fixture-file")
        for cid, mid, session_id in (
            (conversation, "private", owner),
            (conversation, "shared", owner),
            (sibling, "shared", owner),
            (other, "other", stranger),
        ):
            await uow.conversations.link_media(session_id, cid, mid)
        await uow.commit()
    await CatalogService(lambda: PostgresUnitOfWork(factory)).create(bundle())
    (media_root / "fixture-1.png").write_bytes(b"catalog-file")
    return owner, stranger, conversation, sibling, other


async def write_checkpoint(database_url, conversation_id):
    await setup_checkpoints(database_url)
    async with checkpoint_saver(database_url) as saver:
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {"profile": {"context": "fixture"}}
        checkpoint["channel_versions"] = {"profile": "1"}
        config = await saver.aput(
            {"configurable": {"thread_id": str(conversation_id), "checkpoint_ns": ""}},
            checkpoint,
            {"source": "input", "step": 0, "parents": {}},
            {"profile": "1"},
        )
        await saver.aput_writes(config, [("message", "fixture")], "task")


async def checkpoint_counts(connection, conversation_id):
    counts = []
    for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        counts.append(
            (
                await connection.execute(
                    text(
                        f"SELECT count(*) FROM foodwise_checkpoints.{table} WHERE thread_id = :thread"
                    ),
                    {"thread": str(conversation_id)},
                )
            ).scalar_one()
        )
    return tuple(counts)


@pytest.mark.asyncio
async def test_delete_erases_owned_context_checkpoints_and_unshared_files(
    repositories, database_url, tmp_path
):
    factory, connection = repositories
    owner, stranger, conversation, sibling, other = await seed(factory, tmp_path)
    await write_checkpoint(database_url, conversation)
    await write_checkpoint(database_url, sibling)
    try:
        assert all(
            count > 0 for count in await checkpoint_counts(connection, conversation)
        )
        cleanup = MediaCleanupService(
            lambda: PostgresUnitOfWork(factory), LocalMediaFiles(tmp_path)
        )
        service = ConversationService(lambda: PostgresUnitOfWork(factory), cleanup)
        result = await service.delete(owner, conversation)
        assert not result.cleanup_pending
        assert await checkpoint_counts(connection, conversation) == (0, 0, 0)
        assert all(count > 0 for count in await checkpoint_counts(connection, sibling))
        for model in (Conversation, Message, Profile, ConversationMedia):
            key = model.id if model is Conversation else model.conversation_id
            assert (
                await connection.execute(select(key).where(key == conversation))
            ).all() == []
        assert set((await connection.execute(select(Media.id))).scalars()) == {
            "shared",
            "other",
            "image-1",
        }
        assert not (tmp_path / "private.png").exists()
        for name in ("shared.png", "other.png", "fixture-1.png"):
            assert (tmp_path / name).exists()
        assert (await connection.execute(select(Recipe.id))).scalar_one() == "1"
        assert (await connection.execute(select(Document.id))).scalar_one() == "doc-1"
        assert (
            await connection.execute(select(SourceRecord.id))
        ).scalar_one() == "record-1"
        assert (
            await connection.execute(select(MediaCleanupJob.storage_key))
        ).all() == []
        # The shared upload is removed only after its final conversation goes.
        second_result = await service.delete(owner, sibling)
        assert not second_result.cleanup_pending
        assert not (tmp_path / "shared.png").exists()
        assert await checkpoint_counts(connection, sibling) == (0, 0, 0)
        assert (tmp_path / "other.png").exists()
        with pytest.raises(ApplicationError) as failure:
            await service.delete(owner, conversation)
        assert failure.value.code == ErrorCode.NOT_FOUND
    finally:
        await connection.rollback()
        async with checkpoint_saver(database_url) as saver:
            await saver.adelete_thread(str(conversation))
            await saver.adelete_thread(str(sibling))


@pytest.mark.asyncio
async def test_unauthorized_delete_and_post_checkpoint_failure_leave_everything(
    repositories, database_url, tmp_path
):
    factory, connection = repositories
    owner, stranger, conversation, _, _ = await seed(factory, tmp_path)
    await write_checkpoint(database_url, conversation)
    try:
        service = ConversationService(lambda: PostgresUnitOfWork(factory))
        with pytest.raises(ApplicationError) as failure:
            await service.delete(stranger, conversation)
        assert failure.value.code == ErrorCode.NOT_FOUND
        with pytest.raises(RuntimeError, match="abort"):
            async with PostgresUnitOfWork(factory) as uow:
                await uow.conversations.delete(owner, conversation)
                assert await checkpoint_counts(connection, conversation) == (0, 0, 0)
                raise RuntimeError("abort")
        assert all(
            count > 0 for count in await checkpoint_counts(connection, conversation)
        )
        assert (
            await connection.execute(
                select(Conversation.id).where(Conversation.id == conversation)
            )
        ).scalar_one() == conversation
        assert (tmp_path / "private.png").exists()
        assert (
            await connection.execute(select(MediaCleanupJob.storage_key))
        ).all() == []
    finally:
        await connection.rollback()
        async with checkpoint_saver(database_url) as saver:
            await saver.adelete_thread(str(conversation))


@pytest.mark.asyncio
async def test_failed_file_cleanup_stays_queued_and_retry_is_idempotent(
    repositories, database_url, tmp_path
):
    factory, connection = repositories
    owner, _, conversation, _, _ = await seed(factory, tmp_path)
    await setup_checkpoints(database_url)

    class FailingFiles:
        async def delete(self, storage_key):
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)

    worker = MediaCleanupService(lambda: PostgresUnitOfWork(factory), FailingFiles())
    result = await ConversationService(
        lambda: PostgresUnitOfWork(factory), worker
    ).delete(owner, conversation)
    assert result.cleanup_pending
    assert (
        await connection.execute(select(MediaCleanupJob.storage_key))
    ).scalar_one() == "private.png"
    assert (tmp_path / "private.png").exists()
    successful = MediaCleanupService(
        lambda: PostgresUnitOfWork(factory), LocalMediaFiles(tmp_path)
    )
    assert (await successful.run()).failed == 0
    assert not (tmp_path / "private.png").exists()
    assert (await successful.run()).removed == 0


@pytest.mark.asyncio
async def test_cleanup_preserves_referenced_storage_and_removes_symlink_only(
    repositories, tmp_path
):
    factory, connection = repositories
    await CatalogService(lambda: PostgresUnitOfWork(factory)).create(bundle())
    (tmp_path / "fixture-1.png").write_bytes(b"catalog")
    outside = tmp_path.parent / f"outside-{uuid4()}"
    outside.write_bytes(b"keep")
    (tmp_path / "symlink.png").symlink_to(outside)
    await connection.execute(
        insert(MediaCleanupJob),
        [{"storage_key": "fixture-1.png"}, {"storage_key": "symlink.png"}],
    )
    try:
        result = await MediaCleanupService(
            lambda: PostgresUnitOfWork(factory), LocalMediaFiles(tmp_path)
        ).run()
        assert result.retained == 1 and result.removed == 1
        assert (tmp_path / "fixture-1.png").read_bytes() == b"catalog"
        assert outside.read_bytes() == b"keep"
        assert not (tmp_path / "symlink.png").exists()
    finally:
        outside.unlink()


@pytest.mark.asyncio
async def test_checkpoint_failure_rolls_back_context_and_media(
    repositories, database_url, tmp_path, monkeypatch
):
    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    factory, connection = repositories
    owner, _, conversation, _, _ = await seed(factory, tmp_path)
    await setup_checkpoints(database_url)

    async def unavailable(self, thread_id):
        raise psycopg.OperationalError("synthetic unavailable checkpoints")

    monkeypatch.setattr(AsyncPostgresSaver, "adelete_thread", unavailable)
    with pytest.raises(ApplicationError) as failure:
        await ConversationService(lambda: PostgresUnitOfWork(factory)).delete(
            owner, conversation
        )
    assert failure.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert (
        await connection.execute(
            select(Conversation.id).where(Conversation.id == conversation)
        )
    ).scalar_one() == conversation
    assert (
        await connection.execute(
            select(Message.id).where(Message.conversation_id == conversation)
        )
    ).scalar_one()
    assert (
        await connection.execute(select(Media.id).where(Media.id == "private"))
    ).scalar_one() == "private"
    assert (tmp_path / "private.png").exists()
    assert (await connection.execute(select(MediaCleanupJob.storage_key))).all() == []


@pytest.mark.asyncio
async def test_committed_erasure_survives_reopened_database_connection(
    database_url, tmp_path
):
    import hashlib

    from alembic import command
    from alembic.config import Config
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from food_recommender.domain.catalog import PreparedCatalog, RecipeData
    from food_recommender.infrastructure.persistence.engine import (
        create_database_engine,
    )
    from food_recommender.infrastructure.persistence.models.context import (
        BrowserSession,
    )

    engine = create_database_engine(database_url)
    owner, conversation, catalog_id = uuid4(), uuid4(), str(uuid4())
    media_id = f"committed-{uuid4()}"
    storage_key = f"{media_id}.png"
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    def transactions():
        return PostgresUnitOfWork(sessions)

    try:
        async with engine.begin() as connection:

            def migrate(conn):
                config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
                config.attributes["connection"] = conn
                command.upgrade(config, "head")

            await connection.run_sync(migrate)
        async with transactions() as uow:
            await uow.conversations.create_session(
                owner, hashlib.sha256(str(owner).encode()).hexdigest()
            )
            await uow.conversations.create(owner, conversation)
            await uow.conversations.save_profile(
                owner, conversation, Preferences(location="California")
            )
            await uow.conversations.append_message(
                owner, conversation, uuid4(), "user", "Dinner"
            )
            await uow.session.execute(
                insert(Media).values(
                    id=media_id,
                    owner_session_id=owner,
                    storage_key=storage_key,
                    mime_type="image/png",
                    byte_size=10,
                    width=2,
                    height=2,
                    content_hash="a" * 64,
                    ingestion_version="upload-v1",
                    attribution="source",
                )
            )
            await uow.conversations.link_media(owner, conversation, media_id)
            await uow.catalog.create(
                PreparedCatalog(
                    RecipeData(
                        id=catalog_id,
                        source_id="committed-fixture",
                        source_record_id=catalog_id,
                        name="Keep catalog",
                    )
                )
            )
            await uow.commit()
        (tmp_path / storage_key).write_bytes(b"fixture")
        await write_checkpoint(database_url, conversation)
        result = await ConversationService(
            transactions, MediaCleanupService(transactions, LocalMediaFiles(tmp_path))
        ).delete(owner, conversation)
        assert not result.cleanup_pending
        await engine.dispose()  # Reopen rather than reusing the old pooled connection.
        async with engine.connect() as connection:
            assert await checkpoint_counts(connection, conversation) == (0, 0, 0)
            for model in (Conversation, Message, Profile, ConversationMedia):
                key = model.id if model is Conversation else model.conversation_id
                assert (
                    await connection.execute(select(key).where(key == conversation))
                ).all() == []
            assert (
                await connection.execute(select(Media.id).where(Media.id == media_id))
            ).all() == []
            assert (
                await connection.execute(
                    select(Recipe.id).where(Recipe.id == catalog_id)
                )
            ).scalar_one() == catalog_id
            assert (
                await connection.execute(
                    select(MediaCleanupJob.storage_key).where(
                        MediaCleanupJob.storage_key == storage_key
                    )
                )
            ).all() == []
        assert not (tmp_path / storage_key).exists()
    finally:
        from sqlalchemy import delete

        async with checkpoint_saver(database_url) as saver:
            await saver.adelete_thread(str(conversation))
        async with engine.begin() as connection:
            await connection.execute(
                delete(Conversation).where(Conversation.id == conversation)
            )
            await connection.execute(delete(Media).where(Media.id == media_id))
            await connection.execute(
                delete(BrowserSession).where(BrowserSession.id == owner)
            )
            await connection.execute(delete(Recipe).where(Recipe.id == catalog_id))
            await connection.execute(
                delete(MediaCleanupJob).where(
                    MediaCleanupJob.storage_key == storage_key
                )
            )
        await engine.dispose()
