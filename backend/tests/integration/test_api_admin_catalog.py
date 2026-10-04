"""Explicit preview and catalog mutation, version and delete intent contracts."""

from dataclasses import replace

import pytest
from test_api_conversations import api  # noqa: F401
from test_repositories import repositories  # noqa: F401

from food_recommender.application.admin import AdminService
from food_recommender.application.admin_catalog import AdminCatalogService
from food_recommender.application.browse import BrowseService
from food_recommender.application.catalog import CatalogService
from food_recommender.application.catalog_preparation import CatalogPreparation
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
            CatalogPreparation(),
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
