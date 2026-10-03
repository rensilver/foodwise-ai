from dataclasses import replace
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.application.errors import ApplicationError
from food_recommender.infrastructure.catalog import Recipe, Restaurant, Review
from food_recommender.infrastructure.ingestion import (
    IngestionCheckpoint,
    PostgresIngestionStore,
)
from food_recommender.infrastructure.persistence import create_database_engine
from food_recommender.infrastructure.provenance import SourceRecord
from food_recommender.ingestion.adapters import (
    adapt_recipe,
    adapt_restaurant,
    adapt_review,
)
from food_recommender.ingestion.models import SeedItem
from food_recommender.ingestion.seed import artifact, source_record


@pytest_asyncio.fixture
async def seed_store(database_url):
    engine = create_database_engine(database_url)
    async with engine.connect() as connection:
        transaction = await connection.begin()

        def migrate(conn):
            config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
            config.attributes["connection"] = conn
            command.upgrade(config, "head")

        await connection.run_sync(migrate)
        sessions = async_sessionmaker(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield PostgresIngestionStore(sessions), connection
        await transaction.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_hash_upsert_is_atomic_and_repeated_import_does_not_change_versions(
    seed_store, tmp_path
):
    store, connection = seed_store
    raw = {"id": 1, "name": "Soup"}
    path = tmp_path / "Recipes.json"
    path.write_text('[{"id":1,"name":"Soup"}]')
    source = artifact(path, "course-recipes").source
    record = source_record(source, "recipe", "1", raw=raw)
    item = SeedItem(
        adapt_recipe(raw, path.name).data, (source,), (record,), inputs=(raw,)
    )
    assert await store.upsert(item) == "imported"
    assert await store.upsert(item) == "unchanged"
    assert (await connection.execute(select(Recipe.version))).scalar_one() == 1
    changed = replace(item, data=replace(item.data, name="Changed"))
    assert await store.upsert(changed) == "imported"
    assert (await connection.execute(select(Recipe.version))).scalar_one() == 2
    invalid = replace(
        changed,
        data=replace(changed.data, name="Rollback"),
        records=({**record, "content_hash": "invalid"},),
    )
    with pytest.raises(Exception):
        await store.upsert(invalid)
    assert (await connection.execute(select(Recipe.name))).scalar_one() == "Changed"
    assert (
        await connection.execute(select(IngestionCheckpoint.fingerprint))
    ).scalar_one() == changed.fingerprint
    assert (
        await connection.execute(select(func.count()).select_from(SourceRecord))
    ).scalar_one() == 1


@pytest.mark.asyncio
async def test_manual_edits_conflict_and_review_relationships_survive(seed_store):
    store, connection = seed_store
    restaurant = SeedItem(adapt_restaurant({"itemId": 5, "name": "Cafe"}, "r").data)
    review = SeedItem(
        adapt_review(
            {"reviewId": 9, "itemId": 5, "userId": "demo", "text": "Nice"}, "v"
        ).data
    )
    await store.upsert(restaurant)
    await store.upsert(review)
    await store.upsert(
        replace(restaurant, data=replace(restaurant.data, name="New cafe"))
    )
    assert (await connection.execute(select(Review.restaurant_id))).scalar_one() == "5"
    await connection.execute(update(Restaurant).values(version=3, name="Admin edit"))
    with pytest.raises(ApplicationError):
        await store.upsert(restaurant)
    assert (
        await connection.execute(select(Restaurant.name))
    ).scalar_one() == "Admin edit"
