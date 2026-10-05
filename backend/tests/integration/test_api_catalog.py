"""Paginated category-specific browsing with source-backed details."""

from dataclasses import replace

import pytest
from test_api_conversations import api  # noqa: F401
from test_repositories import bundle, repositories  # noqa: F401

from food_recommender.application.catalog.browse import BrowseService
from food_recommender.application.catalog.service import CatalogService
from food_recommender.domain.catalog import PreparedCatalog, RestaurantData
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


@pytest.mark.asyncio
async def test_browse_filters_pagination_and_source_details(api, repositories):  # noqa: F811
    client, app, services = api
    factory, _ = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    app.state.services = replace(services, browse=BrowseService(transactions))
    catalog = CatalogService(transactions)
    await catalog.create(bundle("1"))
    await catalog.create(bundle("2", name="Tomato Rice"))
    await catalog.create(
        PreparedCatalog(
            RestaurantData(
                id="1",
                source_id="fixture",
                source_record_id="1",
                name="Cafe",
                cuisine="Italian",
                normalized_cuisine="italian",
                location="LA",
                normalized_location="la",
                price_band=2,
            )
        )
    )
    page = await client.get("/api/v1/recipes?limit=1&offset=1")
    assert page.status_code == 200
    assert page.json()["total"] == 2
    assert page.json()["items"][0]["data"]["id"] == "2"
    detail = (await client.get("/api/v1/recipes/1")).json()
    assert detail["data"]["ingredients"] == ["rice", "peas"]
    assert detail["citations"][0]["document_id"] == "doc-1"
    assert detail["citations"][0]["excerpt"] == "Rice and peas"
    assert "storage_key" not in str(detail)
    assert (
        await client.get("/api/v1/restaurants?cuisine=Italian&location=LA&price_band=2")
    ).json()["total"] == 1
    assert (await client.get("/api/v1/restaurants?price_band=1")).json()["total"] == 0
    assert (await client.get("/api/v1/recipes/absent")).status_code == 404
    for query in ("location=LA", "price_band=2", "limit=101", "offset=-1", "unknown=x"):
        assert (await client.get("/api/v1/recipes?" + query)).status_code == 422
