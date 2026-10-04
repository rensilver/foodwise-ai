"""Decoded upload ownership, metadata stripping and hostile inputs."""

import io
from dataclasses import replace

import httpx
import pytest
from PIL import Image, PngImagePlugin
from test_api_conversations import api  # noqa: F401
from test_repositories import repositories  # noqa: F401

from food_recommender.application.media import MediaService
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.media.uploads import ImageSanitizer
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


@pytest.mark.asyncio
async def test_upload_private_read_and_metadata_stripping(api, repositories, tmp_path):  # noqa: F811
    client, app, services = api
    factory, _ = repositories
    app.state.services = replace(
        services,
        media=MediaService(
            lambda: PostgresUnitOfWork(factory),
            LocalMediaFiles(tmp_path),
            ImageSanitizer(),
        ),
    )
    data = io.BytesIO()
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("private", "location-secret")
    Image.new("RGB", (3, 2)).save(data, format="PNG", pnginfo=metadata)
    uploaded = await client.post(
        "/api/v1/media",
        files={"file": ("../../unsafe.png", data.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201
    receipt = uploaded.json()
    assert receipt["width"] == 3 and receipt["height"] == 2
    assert "storage_key" not in uploaded.text
    image = await client.get("/api/v1/media/" + receipt["id"])
    assert image.status_code == 200
    assert image.headers["cache-control"] == "private, no-store"
    assert "private" not in Image.open(io.BytesIO(image.content)).info
    assert "location-secret" not in str(image.content)
    assert len(list(tmp_path.iterdir())) == 1
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as stranger:
        await stranger.post("/api/v1/conversations")
        assert (await stranger.get("/api/v1/media/" + receipt["id"])).status_code == 404
    for content, mime in (
        (b"not an image", "image/png"),
        (data.getvalue(), "text/plain"),
        (b"x" * (10 * 1024 * 1024 + 1), "image/png"),
    ):
        assert (
            await client.post("/api/v1/media", files={"file": ("a.png", content, mime)})
        ).status_code == 422
    assert len(list(tmp_path.iterdir())) == 1
