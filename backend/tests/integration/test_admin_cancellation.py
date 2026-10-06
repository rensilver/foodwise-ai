"""Release contracts: cancellation cannot leave partially searchable catalog edits."""

# ruff: noqa: F811

import asyncio

import pytest
from sqlalchemy import text
from test_repositories import bundle, repositories  # noqa: F401
from test_text_index import Encoder

from food_recommender.application.catalog.admin import AdminCatalogService
from food_recommender.application.catalog.browse import BrowseService
from food_recommender.application.catalog.preparation import CatalogPreparation
from food_recommender.application.catalog.service import CatalogService
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


async def snapshot(connection):
    # Include vector values, timestamps, provenance and pending media cleanup.
    return {
        table: (
            await connection.execute(
                text(
                    f"SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text"
                )
            )
        )
        .scalars()
        .all()
        for table in (
            "recipes",
            "sources",
            "source_records",
            "documents",
            "media",
            "text_embeddings",
            "image_embeddings",
            "media_cleanup_jobs",
        )
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "edit", "delete"])
async def test_cancel_after_sql_before_commit_preserves_every_row(
    repositories, operation
):  # noqa: F811
    factory, connection = repositories
    normal = CatalogService(lambda: PostgresUnitOfWork(factory))
    await normal.create(bundle())
    before = await snapshot(connection)
    reached_commit = asyncio.Event()

    class PausedCommit(PostgresUnitOfWork):
        async def commit(self):
            reached_commit.set()
            await asyncio.Future()

    service = CatalogService(lambda: PausedCommit(factory))
    ref = EntityRef(Category.RECIPE, "1")
    action = {
        "create": lambda: service.create(bundle("2")),
        "edit": lambda: service.replace(
            ref, bundle(name="Tomato rice", description="Tomatoes"), expected_version=1
        ),
        "delete": lambda: service.delete(ref, expected_version=1),
    }[operation]
    task = asyncio.create_task(action())
    try:
        await asyncio.wait_for(reached_commit.wait(), timeout=5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert await snapshot(connection) == before
    # A subsequent ordinary edit proves cancellation also releases the transaction.
    assert (
        await normal.replace(ref, bundle(name="Peas"), expected_version=1)
    ).version == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "edit"])
async def test_cancel_during_preparation_preserves_catalog(repositories, operation):  # noqa: F811
    factory, connection = repositories
    catalog = CatalogService(lambda: PostgresUnitOfWork(factory))
    await catalog.create(bundle())
    before = await snapshot(connection)
    started = asyncio.Event()
    preparation = CatalogPreparation(Encoder())

    class PausedPreparation:
        async def prepare(self, data):
            await preparation.prepare(data)
            started.set()
            await asyncio.Future()

    service = AdminCatalogService(
        catalog,
        BrowseService(lambda: PostgresUnitOfWork(factory)),
        PausedPreparation(),
        None,
    )
    ref = EntityRef(Category.RECIPE, "1")
    action = (
        service.create(Category.RECIPE, {"name": "Cancelled create"})
        if operation == "create"
        else service.update(ref, {"name": "Cancelled edit"}, 1)
    )
    task = asyncio.create_task(action)
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert await snapshot(connection) == before
    service.preparer = preparation
    assert (await service.update(ref, {"name": "Recovered rice"}, 1)).version == 2
