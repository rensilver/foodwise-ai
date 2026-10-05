"""Failure, migration, concurrency and ownership acceptance for Phase 2."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from test_repositories import bundle
from test_repositories import repositories as repositories

from food_recommender.application.catalog.service import CatalogService
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.trends.ports import CachedTrends, TrendItem
from food_recommender.domain.catalog import PreparedCatalog, RecipeData, RestaurantData
from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.values import (
    Category,
    ConstraintKind,
    EntityRef,
    Origin,
    Strength,
)
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.models.catalog import (
    Recipe,
    Restaurant,
    Review,
)
from food_recommender.infrastructure.persistence.models.context import DemoProfile
from food_recommender.infrastructure.persistence.models.embeddings import (
    ImageEmbedding,
    TextEmbedding,
)
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    Media,
    SourceRecord,
)
from food_recommender.infrastructure.persistence.models.trends import (
    TrendCache,
    TrendEvidence,
)
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate", ["canonical", "source"])
async def test_duplicate_catalog_identity_rejected_by_adapter(repositories, duplicate):
    factory, connection = repositories
    service = CatalogService(lambda: PostgresUnitOfWork(factory))
    await service.create(bundle())
    data = bundle("2").data
    data = (
        replace(data, id="1")
        if duplicate == "canonical"
        else replace(data, source_record_id="1")
    )
    with pytest.raises(ApplicationError) as failure:
        await service.create(PreparedCatalog(data))
    assert failure.value.code == ErrorCode.CONFLICT
    assert (await connection.execute(select(Recipe.id))).scalars().all() == ["1"]


@pytest.mark.asyncio
async def test_failed_replacement_preserves_all_old_rows_and_version(repositories):
    factory, connection = repositories
    service = CatalogService(lambda: PostgresUnitOfWork(factory))
    await service.create(bundle())
    await service.create(bundle("2"))
    with pytest.raises(ApplicationError) as failure:
        await service.replace(
            EntityRef(Category.RECIPE, "1"),
            bundle(description="Modified", document_id="doc-2"),
            expected_version=1,
        )
    assert failure.value.code == ErrorCode.CONFLICT
    assert (
        await connection.execute(select(Recipe.version).where(Recipe.id == "1"))
    ).scalar_one() == 1
    assert (
        await connection.execute(select(Document.text).where(Document.id == "doc-1"))
    ).scalar_one() == "Rice and peas"
    for model in (Media, TextEmbedding, ImageEmbedding):
        assert len((await connection.execute(select(model.id))).all()) == 2


@pytest.mark.asyncio
async def test_cancelled_transaction_rolls_back_prepared_write(repositories):
    factory, connection = repositories
    with pytest.raises(asyncio.CancelledError):
        async with PostgresUnitOfWork(factory) as uow:
            await uow.catalog.create(bundle())
            raise asyncio.CancelledError()
    for model in (Recipe, SourceRecord, Document, Media, TextEmbedding, ImageEmbedding):
        assert (await connection.execute(select(model.id))).all() == []


@pytest.mark.asyncio
async def test_linked_review_prevents_catalog_delete_and_rolls_back_cleanup(
    repositories,
):
    factory, connection = repositories
    service = CatalogService(lambda: PostgresUnitOfWork(factory))
    prepared = bundle()
    prepared = replace(
        prepared,
        data=RestaurantData(
            id="1", source_id="course", source_record_id="1", name="Place"
        ),
        records=(replace(prepared.records[0], record_type="restaurant"),),
    )
    await service.create(prepared)
    await connection.execute(insert(DemoProfile), dict(id="demo"))
    await connection.execute(
        insert(Review),
        dict(
            id="review",
            source_id="course",
            source_record_id="review",
            restaurant_id="1",
            demo_profile_id="demo",
            text="Dinner",
        ),
    )
    with pytest.raises(ApplicationError) as failure:
        await service.delete(EntityRef(Category.RESTAURANT, "1"), expected_version=1)
    assert failure.value.code == ErrorCode.INVALID_REQUEST
    assert (await connection.execute(select(Restaurant.version))).scalar_one() == 1
    assert (await connection.execute(select(Document.id))).scalar_one() == "doc-1"
    assert (
        await connection.execute(select(SourceRecord.restaurant_id))
    ).scalar_one() == "1"
    assert (
        await connection.execute(select(ImageEmbedding.id))
    ).scalar_one() == "clip-1"


@pytest.mark.asyncio
async def test_two_competing_versions_have_exactly_one_winner(database_url):
    # Commit migrations to this disposable database; each contender gets its own
    # pooled connection and transaction, exercising PostgreSQL's row locking.
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        from pathlib import Path

        from alembic.config import Config

        def migrate(conn):
            config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
            config.attributes["connection"] = conn
            command.upgrade(config, "head")

        await connection.run_sync(migrate)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = CatalogService(lambda: PostgresUnitOfWork(sessions))
    identity = str(uuid4())
    original = RecipeData(
        id=identity,
        source_id="concurrency-fixture",
        source_record_id=identity,
        name="Initial",
    )
    ref = EntityRef(Category.RECIPE, identity)
    try:
        await service.create(PreparedCatalog(original))
        results = await asyncio.gather(
            *(
                service.replace(
                    ref,
                    PreparedCatalog(replace(original, name=name)),
                    expected_version=1,
                )
                for name in ("First", "Second")
            ),
            return_exceptions=True,
        )
        assert sum(not isinstance(result, BaseException) for result in results) == 1
        failure = next(
            result for result in results if isinstance(result, ApplicationError)
        )
        assert failure.code == ErrorCode.CONFLICT
        async with PostgresUnitOfWork(sessions) as uow:
            result = await uow.catalog.get(ref)
            assert result.version == 2 and result.data.name in {"First", "Second"}
    finally:
        async with engine.begin() as connection:
            await connection.execute(delete(Recipe).where(Recipe.id == identity))
        await engine.dispose()


@pytest.mark.asyncio
async def test_restrictions_roundtrip_and_unauthorized_mutations_are_rejected(
    repositories,
):
    factory, _ = repositories
    owner, stranger, conversation_id = uuid4(), uuid4(), uuid4()
    preferences = Preferences(
        constraints=(
            Constraint(
                ConstraintKind.ALLERGEN, "peanut", Strength.HARD, Origin.EXPLICIT
            ),
        )
    )
    async with PostgresUnitOfWork(factory) as uow:
        await uow.conversations.create_session(owner, "a" * 64)
        await uow.conversations.create_session(stranger, "b" * 64)
        await uow.conversations.create(owner, conversation_id)
        await uow.conversations.save_profile(owner, conversation_id, preferences)
        await uow.commit()
    for operation in ("message", "media"):
        with pytest.raises(ApplicationError) as failure:
            async with PostgresUnitOfWork(factory) as uow:
                if operation == "message":
                    await uow.conversations.append_message(
                        stranger, conversation_id, uuid4(), "user", "Overwrite"
                    )
                else:
                    await uow.conversations.link_media(
                        stranger, conversation_id, "missing"
                    )
                await uow.commit()
        assert failure.value.code == ErrorCode.NOT_FOUND
    async with PostgresUnitOfWork(factory) as uow:
        assert (
            await uow.conversations.get_profile(owner, conversation_id) == preferences
        )
        assert await uow.conversations.messages(owner, conversation_id) == ()
        assert await uow.conversations.resolve_session("a" * 64) == owner
        assert await uow.conversations.resolve_session("c" * 64) is None


@pytest.mark.asyncio
async def test_cache_expiry_boundaries_and_failed_refresh_preserve_evidence(
    repositories,
):
    factory, connection = repositories
    now = datetime(2026, 10, 3, tzinfo=UTC)
    first = CachedTrends(
        "a" * 64,
        "mushrooms",
        now,
        now + timedelta(hours=24),
        (
            TrendItem(
                uuid4(), "https://example.test/article", "Mushroom evidence", None, now
            ),
        ),
    )
    async with PostgresUnitOfWork(factory) as uow:
        await uow.trends.put(first)
        await uow.commit()
    async with PostgresUnitOfWork(factory) as uow:
        assert await uow.trends.get(first.query_hash, now) == first
        assert (
            await uow.trends.get(first.query_hash, now - timedelta(seconds=1)) is None
        )
        assert await uow.trends.get(first.query_hash, first.expires_at) is None
        assert (
            await uow.trends.get(
                first.query_hash, first.expires_at - timedelta(seconds=1)
            )
            == first
        )
    invalid = replace(
        first,
        query="replacement",
        evidence=(replace(first.evidence[0], url="file:///private"),),
    )
    with pytest.raises(ApplicationError) as failure:
        async with PostgresUnitOfWork(factory) as uow:
            await uow.trends.put(invalid)
            await uow.commit()
    assert failure.value.code == ErrorCode.INVALID_REQUEST
    assert (
        await connection.execute(select(TrendCache.query))
    ).scalar_one() == "mushrooms"
    assert (
        await connection.execute(select(TrendEvidence.url))
    ).scalar_one() == "https://example.test/article"


def test_upgrade_backfills_legacy_demo_profile_without_changing_catalog(catalog):
    connection, config = catalog
    command.downgrade(config, "0004_search")
    connection.execute(
        insert(Restaurant).values(
            id="legacy",
            source_id="course",
            source_record_id="legacy",
            name="Legacy place",
        )
    )
    # Use table-level SQL because pre-upgrade rows have no version column.
    connection.exec_driver_sql(
        "INSERT INTO reviews (id, source_id, source_record_id, restaurant_id, demo_profile_id, text) VALUES ('legacy', 'course', 'legacy', 'legacy', 'legacy-profile', 'Original review')"
    )
    command.upgrade(config, "head")
    assert connection.execute(select(DemoProfile.id)).scalar_one() == "legacy-profile"
    assert connection.execute(select(Review.version)).scalar_one() == 1
    assert connection.execute(select(Review.text)).scalar_one() == "Original review"
    assert connection.execute(select(Restaurant.name)).scalar_one() == "Legacy place"


@pytest.mark.parametrize(
    "model,payload",
    [
        (
            Recipe,
            dict(
                id="1", source_id="course", source_record_id="1", name="Dish", version=0
            ),
        ),
        (
            Restaurant,
            dict(
                id="1",
                source_id="course",
                source_record_id="1",
                name="Place",
                version=-1,
            ),
        ),
    ],
)
def test_database_rejects_nonpositive_versions(catalog, model, payload):
    connection, _ = catalog
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(model), payload)
