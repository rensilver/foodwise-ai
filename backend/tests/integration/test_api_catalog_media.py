"""Catalog images are delivered only through their actual entity association."""

# ruff: noqa: F811
import io
from dataclasses import replace

import pytest
from PIL import Image
from test_api_conversations import api  # noqa: F401
from test_repositories import bundle, repositories  # noqa: F401

from food_recommender.application.catalog.browse import BrowseService
from food_recommender.application.catalog.service import CatalogService
from food_recommender.application.media.service import MediaService
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.media.uploads import ImageSanitizer
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


@pytest.mark.asyncio
async def test_catalog_receipts_entity_scoping_and_private_upload_exclusion(
    api, repositories, tmp_path
):
    client, app, services = api
    factory, _ = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    files = LocalMediaFiles(tmp_path)
    app.state.services = replace(
        services,
        browse=BrowseService(transactions),
        media=MediaService(transactions, files, ImageSanitizer()),
    )
    image = io.BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    await CatalogService(transactions).create(bundle("1"))
    await CatalogService(transactions).create(bundle("2"))
    await files.write("fixture-1.png", image.getvalue())
    detail = (await client.get("/api/v1/recipes/1")).json()
    assert detail["images"][0]["id"] == "image-1"
    assert "storage_key" not in str(detail)
    good = await client.get("/api/v1/recipes/1/images/image-1")
    assert (
        good.status_code == 200 and good.headers["cache-control"] == "private, no-store"
    )
    assert (await client.get("/api/v1/recipes/2/images/image-1")).status_code == 404
    assert (await client.get("/api/v1/restaurants/1/images/image-1")).status_code == 404
    upload = await client.post(
        "/api/v1/media", files={"file": ("x.png", image.getvalue(), "image/png")}
    )
    assert (
        await client.get("/api/v1/recipes/1/images/" + upload.json()["id"])
    ).status_code == 404
    assert (await client.get("/api/v1/media/image-1")).status_code == 404
