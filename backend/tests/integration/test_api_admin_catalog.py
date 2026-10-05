"""Explicit preview and catalog mutation, version and delete intent contracts."""

# ruff: noqa: F811

from dataclasses import replace

import pytest
from test_api_conversations import api  # noqa: F401
from test_repositories import repositories  # noqa: F401
from test_text_index import Encoder

from food_recommender.application.auth.service import AdminService
from food_recommender.application.catalog.admin import AdminCatalogService
from food_recommender.application.catalog.browse import BrowseService
from food_recommender.application.catalog.preparation import CatalogPreparation
from food_recommender.application.catalog.service import CatalogService
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.ingestion.extraction import ExtractionResult


class Passwords:
    async def verify(self, password):
        return password == "fixture"


class Preview:
    async def preview(self, text, category):
        return ExtractionResult(
            status="validated",
            source="admin-preview",
            record_id="preview",
            input_hash="a" * 64,
            model="fixture",
            attempts=1,
            fields={"name": "Rice", "ingredients": ["rice"]},
        )


@pytest.mark.asyncio
async def test_preview_crud_expected_version_and_delete_intent(api, repositories):  # noqa: F811
    client, app, services = api
    factory, _ = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    app.state.services = replace(
        services,
        admin=AdminService(transactions, Passwords()),
        admin_catalog=AdminCatalogService(
            CatalogService(transactions),
            BrowseService(transactions),
            CatalogPreparation(Encoder()),
            Preview(),
        ),
        browse=BrowseService(transactions),
    )
    origin = {"origin": "http://localhost"}
    login = await client.post(
        "/api/v1/admin/session", json={"password": "fixture"}, headers=origin
    )
    headers = {**origin, "x-csrf-token": login.json()["csrf_token"]}
    preview = await client.post(
        "/api/v1/admin/extractions/preview",
        json={"category": "recipe", "text": "A rice recipe"},
        headers=headers,
    )
    assert preview.status_code == 200
    assert (await client.get("/api/v1/recipes")).json()["total"] == 0
    created = await client.post(
        "/api/v1/admin/recipes",
        json={
            "fields": {"name": "Rice", "ingredients": ["rice"], "directions": ["Boil"]}
        },
        headers=headers,
    )
    assert created.status_code == 201
    identity = created.json()["data"]["id"]
    assert created.json()["version"] == 1
    path = "/api/v1/admin/recipes/" + identity
    changed = await client.patch(
        path,
        json={"expected_version": 1, "fields": {"name": "Tomato rice"}},
        headers=headers,
    )
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert changed.json()["data"]["ingredients"] == ["rice"]
    assert (
        await client.patch(
            path,
            json={"expected_version": 1, "fields": {"name": "Old"}},
            headers=headers,
        )
    ).status_code == 409
    assert (await client.delete(path, headers=headers)).status_code == 422
    assert (
        await client.request(
            "DELETE",
            path,
            json={"expected_version": 2, "confirm_id": "wrong"},
            headers=headers,
        )
    ).status_code == 422
    assert (
        await client.request(
            "DELETE",
            path,
            json={"expected_version": 2, "confirm_id": identity},
            headers=headers,
        )
    ).status_code == 204
    assert (await client.get("/api/v1/recipes/" + identity)).status_code == 404
    assert (
        await client.post(
            "/api/v1/admin/recipes", json={"fields": {"name": "Rice"}}, headers=origin
        )
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/recipes",
            json={"fields": {"name": "Rice", "id": "invented"}},
            headers=headers,
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_embedding_preparation_and_late_write_failure_are_atomic(
    api, repositories
):  # noqa: F811
    from sqlalchemy import select
    from test_text_index import Encoder

    from food_recommender.domain.values import Category, EntityRef
    from food_recommender.infrastructure.persistence.models.embeddings import (
        TextEmbedding,
    )
    from food_recommender.infrastructure.persistence.models.provenance import Document

    client, app, services = api
    factory, connection = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    preparation = CatalogPreparation(Encoder())
    admin_catalog = AdminCatalogService(
        CatalogService(transactions),
        BrowseService(transactions),
        preparation,
        Preview(),
    )
    created = await admin_catalog.create(
        Category.RECIPE, {"name": "Rice", "ingredients": ["rice"]}
    )
    ref = EntityRef(Category.RECIPE, created.data.id)
    before = (await connection.execute(select(Document.id, Document.text))).all()
    assert len((await connection.execute(select(TextEmbedding.id))).all()) == 1

    class BrokenEncoder(Encoder):
        def encode(self, texts):
            raise RuntimeError("encoding failure")

    admin_catalog.preparer = CatalogPreparation(BrokenEncoder())
    from food_recommender.application.errors import ApplicationError, ErrorCode

    with pytest.raises(ApplicationError) as failure:
        await admin_catalog.update(ref, {"name": "Tomato rice"}, 1)
    assert failure.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert (await admin_catalog.browse.detail(ref)).version == 1
    assert (
        await connection.execute(select(Document.id, Document.text))
    ).all() == before

    # A collision in another entity's document occurs after the update and old
    # retrieval deletion; PostgreSQL must roll all changes back.
    other = await admin_catalog.catalog.create(
        await preparation.prepare(
            replace(created.data, id="other", source_record_id="other")
        )
    )
    collision = (
        await connection.execute(select(Document.id).where(Document.id != before[0][0]))
    ).scalar_one()

    class CollidingPreparation:
        async def prepare(self, data):
            prepared = await preparation.prepare(data)
            return replace(
                prepared,
                documents=(replace(prepared.documents[0], id=collision),),
                text_embeddings=(
                    replace(prepared.text_embeddings[0], parent_id=collision),
                ),
            )

    admin_catalog.preparer = CollidingPreparation()
    with pytest.raises(ApplicationError) as failure:
        await admin_catalog.update(ref, {"name": "Tomato rice"}, 1)
    assert failure.value.code == ErrorCode.CONFLICT
    assert (await admin_catalog.browse.detail(ref)).data.name == "Rice"
    assert (await admin_catalog.browse.detail(ref)).version == 1
    assert (
        await connection.execute(
            select(Document.text).where(Document.id == before[0][0])
        )
    ).scalar_one() == before[0][1]
    assert other.version == 1


@pytest.mark.asyncio
async def test_text_edits_preserve_existing_media_and_noop_provenance(repositories):  # noqa: F811
    from sqlalchemy import select
    from test_repositories import bundle

    from food_recommender.domain.values import Category, EntityRef
    from food_recommender.infrastructure.persistence.models.embeddings import (
        ImageEmbedding,
    )
    from food_recommender.infrastructure.persistence.models.provenance import Media

    factory, connection = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    catalog = CatalogService(transactions)
    await catalog.create(bundle())
    service = AdminCatalogService(
        catalog, BrowseService(transactions), CatalogPreparation(Encoder()), Preview()
    )
    ref = EntityRef(Category.RECIPE, "1")
    assert (await service.update(ref, {"name": "Tomato rice"}, 1)).version == 2
    assert (await service.update(ref, {"name": "Tomato rice"}, 2)).version == 3
    assert (await connection.execute(select(Media.id))).scalars().all() == ["image-1"]
    assert (await connection.execute(select(ImageEmbedding.id))).scalars().all() == [
        "clip-1"
    ]


@pytest.mark.asyncio
async def test_http_embedding_failure_keeps_catalog_and_returns_typed_error(
    api, repositories
):  # noqa: F811
    client, app, services = api
    factory, _ = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    administration = AdminCatalogService(
        CatalogService(transactions),
        BrowseService(transactions),
        CatalogPreparation(Encoder()),
        Preview(),
    )
    app.state.services = replace(
        services,
        admin=AdminService(transactions, Passwords()),
        admin_catalog=administration,
        browse=BrowseService(transactions),
    )
    origin = {"origin": "http://localhost"}
    logged = await client.post(
        "/api/v1/admin/session", json={"password": "fixture"}, headers=origin
    )
    headers = {**origin, "x-csrf-token": logged.json()["csrf_token"]}
    created = await client.post(
        "/api/v1/admin/recipes",
        json={"fields": {"name": "Rice", "ingredients": ["rice"]}},
        headers=headers,
    )
    identity = created.json()["data"]["id"]
    administration.preparer = CatalogPreparation()
    failure = await client.patch(
        "/api/v1/admin/recipes/" + identity,
        json={"expected_version": 1, "fields": {"name": "Peas"}},
        headers=headers,
    )
    assert failure.status_code == 503
    assert failure.json()["error"]["code"] == "dependency_unavailable"
    detail = (await client.get("/api/v1/recipes/" + identity)).json()
    assert detail["version"] == 1 and detail["data"]["name"] == "Rice"
    assert detail["citations"][0]["excerpt"].startswith("name: Rice")


@pytest.mark.asyncio
async def test_restaurant_delete_removes_linked_review_retrieval_atomically(
    repositories,
):  # noqa: F811
    from sqlalchemy import insert, select

    from food_recommender.domain.catalog import PreparedCatalog, RestaurantData
    from food_recommender.domain.values import Category, EntityRef
    from food_recommender.infrastructure.persistence.models.catalog import Review
    from food_recommender.infrastructure.persistence.models.context import DemoProfile
    from food_recommender.infrastructure.persistence.models.provenance import (
        Document,
        Source,
        SourceRecord,
    )

    factory, connection = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    catalog = CatalogService(transactions)
    await catalog.create(
        PreparedCatalog(
            RestaurantData(
                id="restaurant",
                name="Cafe",
                source_id="fixture",
                source_record_id="restaurant",
            )
        )
    )
    await connection.execute(insert(DemoProfile).values(id="fixture-demo"))
    await connection.execute(
        insert(Review).values(
            id="review",
            source_id="fixture",
            source_record_id="review",
            restaurant_id="restaurant",
            demo_profile_id="fixture-demo",
            text="Rice",
        )
    )
    await connection.execute(
        insert(Source).values(
            id="source",
            logical_source_id="fixture",
            locator_kind="file",
            locator="fixture.json",
            content_hash="a" * 64,
        )
    )
    await connection.execute(
        insert(SourceRecord).values(
            id="record",
            source_id="source",
            record_type="review",
            record_id="review",
            review_id="review",
            raw_text="Rice",
            content_hash="a" * 64,
            ingestion_version="fixture",
            attribution="source",
        )
    )
    await connection.execute(
        insert(Document).values(
            id="document",
            source_record_id="record",
            kind="review",
            text="Rice",
            content_hash="a" * 64,
            ingestion_version="fixture",
            attribution="source",
        )
    )
    administration = AdminCatalogService(
        catalog, BrowseService(transactions), CatalogPreparation(Encoder()), Preview()
    )
    await administration.delete(
        EntityRef(Category.RESTAURANT, "restaurant"), 1, "restaurant"
    )
    assert (await connection.execute(select(Review.id))).all() == []
    assert (await connection.execute(select(Document.id))).all() == []
    assert (
        await connection.execute(select(SourceRecord.review_id))
    ).scalar_one() is None
