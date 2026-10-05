"""Observable async repository transaction behavior against PostgreSQL."""

from dataclasses import replace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.application.catalog.service import CatalogService
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.domain.catalog import PreparedCatalog, RecipeData
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.models.catalog import Recipe
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


@pytest_asyncio.fixture
async def repositories(database_url):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    def migration_config():
        return Config(str(Path(__file__).parents[2] / "alembic.ini"))

    engine = create_database_engine(database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        await connection.run_sync(
            lambda conn: _migrate(command, migration_config, conn)
        )
        factory = async_sessionmaker(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield factory, connection
        if transaction.is_active:
            await transaction.rollback()
    await engine.dispose()


def _migrate(command, migration_config, connection):
    config = migration_config()
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


@pytest.mark.asyncio
async def test_catalog_create_replace_versions_and_explicit_rollback(repositories):
    factory, connection = repositories
    service = CatalogService(lambda: PostgresUnitOfWork(factory))
    item = RecipeData(id="1", source_id="course", source_record_id="1", name="Rice")
    result = await service.create(PreparedCatalog(item))
    assert result.version == 1 and result.data == item
    ref = EntityRef(Category.RECIPE, "1")
    updated = await service.replace(
        ref, PreparedCatalog(replace(item, name="Peas")), expected_version=1
    )
    assert updated.version == 2 and updated.data.name == "Peas"
    with pytest.raises(ApplicationError) as failure:
        await service.replace(ref, PreparedCatalog(item), expected_version=1)
    assert failure.value.code == ErrorCode.CONFLICT
    async with PostgresUnitOfWork(factory) as uow:
        await uow.catalog.create(
            PreparedCatalog(
                RecipeData(
                    id="2", source_id="course", source_record_id="2", name="Discarded"
                )
            )
        )
        # No explicit commit: exit rolls back even on success.
    assert (await connection.execute(select(Recipe.id))).scalars().all() == ["1"]


@pytest.mark.asyncio
async def test_conversations_and_profiles_are_scoped_by_session(repositories):
    factory, _ = repositories
    owner, stranger, conversation_id = uuid4(), uuid4(), uuid4()
    async with PostgresUnitOfWork(factory) as uow:
        await uow.conversations.create_session(owner, "a" * 64)
        await uow.conversations.create_session(stranger, "b" * 64)
        await uow.conversations.create(owner, conversation_id)
        await uow.conversations.save_profile(
            owner, conversation_id, Preferences(location="California")
        )
        await uow.conversations.append_message(
            owner, conversation_id, uuid4(), "user", "Dinner"
        )
        await uow.commit()
    async with PostgresUnitOfWork(factory) as uow:
        assert (
            await uow.conversations.get(owner, conversation_id)
        ).id == conversation_id
        assert (
            await uow.conversations.get_profile(owner, conversation_id)
        ).location == "California"
        assert len(await uow.conversations.messages(owner, conversation_id)) == 1
        for call in (
            lambda: uow.conversations.get(stranger, conversation_id),
            lambda: uow.conversations.get_profile(stranger, conversation_id),
            lambda: uow.conversations.messages(stranger, conversation_id),
            lambda: uow.conversations.save_profile(
                stranger, conversation_id, Preferences()
            ),
        ):
            with pytest.raises(ApplicationError) as failure:
                await call()
            assert failure.value.code == ErrorCode.NOT_FOUND


def bundle(identity="1", *, name="Rice", description="Rice and peas", document_id=None):
    import hashlib

    from food_recommender.domain.catalog import (
        DocumentData,
        EmbeddingData,
        MediaData,
        RecordData,
        SourceData,
    )

    digest = hashlib.sha256(description.encode()).hexdigest()
    record_id = f"record-{identity}"
    doc_id = document_id or f"doc-{identity}"
    image_id = f"image-{identity}"
    common = dict(ingestion_version="fixture-v1", attribution="imported")
    return PreparedCatalog(
        RecipeData(
            id=identity,
            source_id="course",
            source_record_id=identity,
            name=name,
            ingredients=("rice", "peas"),
        ),
        sources=(
            SourceData(
                id="file",
                logical_source_id="course",
                locator_kind="file",
                locator="data/fixture.json",
                content_hash="a" * 64,
            ),
        ),
        records=(
            RecordData(
                id=record_id,
                source_id="file",
                record_id=identity,
                record_type="recipe",
                raw_payload={"id": identity},
                content_hash="a" * 64,
                **common,
            ),
        ),
        documents=(
            DocumentData(
                id=doc_id,
                source_record_id=record_id,
                kind="description",
                text=description,
                content_hash=digest,
                **common,
            ),
        ),
        media=(
            MediaData(
                id=image_id,
                source_record_id=record_id,
                storage_key=f"fixture-{identity}.png",
                mime_type="image/png",
                byte_size=32,
                width=2,
                height=2,
                content_hash="a" * 64,
                **common,
            ),
        ),
        text_embeddings=(
            EmbeddingData(
                id=f"text-{identity}",
                parent_id=doc_id,
                model="sentence-transformers/all-MiniLM-L6-v2",
                revision="r1",
                input_hash=digest,
                values=(1.0,) + (0.0,) * 383,
            ),
        ),
        image_embeddings=(
            EmbeddingData(
                id=f"clip-{identity}",
                parent_id=image_id,
                model="openai/clip-vit-base-patch32",
                revision="r1",
                input_hash="a" * 64,
                values=(1.0,) + (0.0,) * 511,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_prepared_catalog_documents_and_vectors_commit_together(repositories):
    from food_recommender.infrastructure.persistence.models.embeddings import (
        ImageEmbedding,
        TextEmbedding,
    )
    from food_recommender.infrastructure.persistence.models.provenance import (
        Document,
        Media,
        SourceRecord,
    )

    factory, connection = repositories
    service = CatalogService(lambda: PostgresUnitOfWork(factory))
    await service.create(bundle())
    assert (
        await connection.execute(select(Document.text))
    ).scalar_one() == "Rice and peas"
    assert (
        len((await connection.execute(select(TextEmbedding.embedding))).scalar_one())
        == 384
    )
    assert (
        len((await connection.execute(select(ImageEmbedding.embedding))).scalar_one())
        == 512
    )
    updated = await service.replace(
        EntityRef(Category.RECIPE, "1"),
        bundle(name="Tomato rice", description="Rice and tomatoes"),
        expected_version=1,
    )
    assert updated.version == 2
    assert (
        await connection.execute(select(Document.text))
    ).scalar_one() == "Rice and tomatoes"
    assert (
        await connection.execute(select(SourceRecord.id))
    ).scalar_one() == "record-1"
    keys = await service.delete(EntityRef(Category.RECIPE, "1"), expected_version=2)
    assert keys == ("fixture-1.png",)
    for model in (Recipe, Document, Media, TextEmbedding, ImageEmbedding):
        assert (await connection.execute(select(model.id))).all() == []
    assert (
        await connection.execute(select(SourceRecord.recipe_id))
    ).scalar_one() is None


@pytest.mark.asyncio
async def test_late_document_failure_rolls_back_entire_prepared_create(repositories):
    from food_recommender.infrastructure.persistence.models.embeddings import (
        TextEmbedding,
    )
    from food_recommender.infrastructure.persistence.models.provenance import (
        Document,
        SourceRecord,
    )

    factory, connection = repositories
    service = CatalogService(lambda: PostgresUnitOfWork(factory))
    await service.create(bundle())
    with pytest.raises(ApplicationError) as failure:
        await service.create(bundle("2", document_id="doc-1"))
    assert failure.value.code == ErrorCode.CONFLICT
    assert (await connection.execute(select(Recipe.id))).scalars().all() == ["1"]
    assert (await connection.execute(select(SourceRecord.id))).scalars().all() == [
        "record-1"
    ]
    assert (await connection.execute(select(Document.id))).scalars().all() == ["doc-1"]
    assert (await connection.execute(select(TextEmbedding.id))).scalars().all() == [
        "text-1"
    ]
