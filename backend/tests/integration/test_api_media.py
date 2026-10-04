"""Decoded upload ownership, metadata stripping and hostile inputs."""

# ruff: noqa: F811

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "format,mime",
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
async def test_all_supported_formats_decode_to_private_metadata_free_images(
    api, repositories, tmp_path, format, mime
):  # noqa: F811
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
    Image.new("RGB", (4, 3)).save(data, format=format)
    result = await client.post(
        "/api/v1/media", files={"file": ("upload", data.getvalue(), mime)}
    )
    assert result.status_code == 201
    clean = await client.get("/api/v1/media/" + result.json()["id"])
    assert Image.open(io.BytesIO(clean.content)).format == "PNG"


@pytest.mark.asyncio
async def test_media_cleanup_after_conversation_delete_and_foreign_media_rejected(
    api, repositories, tmp_path
):  # noqa: F811
    from test_api_messages import Workflow

    from food_recommender.application.conversations import ConversationService
    from food_recommender.application.media_cleanup import MediaCleanupService
    from food_recommender.application.messages import MessageService

    client, app, services = api
    factory, _ = repositories

    def transactions():
        return PostgresUnitOfWork(factory)

    files = LocalMediaFiles(tmp_path)
    cleanup = MediaCleanupService(transactions, files)
    app.state.services = replace(
        services,
        conversations=ConversationService(transactions, cleanup),
        media=MediaService(transactions, files, ImageSanitizer()),
        messages=MessageService(transactions, Workflow()),
    )
    data = io.BytesIO()
    Image.new("RGB", (2, 2)).save(data, format="PNG")
    uploaded = await client.post(
        "/api/v1/media", files={"file": ("upload", data.getvalue(), "image/png")}
    )
    media_id = uploaded.json()["id"]
    conversations = [
        (await client.post("/api/v1/conversations")).json()["id"] for _ in range(2)
    ]
    from uuid import uuid4

    for identity in conversations:
        result = await client.post(
            f"/api/v1/conversations/{identity}/messages",
            json={
                "message": "rice",
                "media_id": media_id,
                "client_request_id": str(uuid4()),
            },
        )
        assert "event: clarification" in result.text
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as stranger:
        identity = (await stranger.post("/api/v1/conversations")).json()["id"]
        assert (
            await stranger.post(
                f"/api/v1/conversations/{identity}/messages",
                json={
                    "message": "rice",
                    "media_id": media_id,
                    "client_request_id": str(uuid4()),
                },
            )
        ).status_code == 404
    assert (
        await client.delete("/api/v1/conversations/" + conversations[0])
    ).status_code == 200
    assert len(list(tmp_path.iterdir())) == 1
    assert (
        await client.delete("/api/v1/conversations/" + conversations[1])
    ).status_code == 200
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_pixel_animation_and_chunked_body_limits_are_enforced_over_http(
    api, repositories, tmp_path
):  # noqa: F811
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
    large = io.BytesIO()
    image = Image.new("RGB", (5000, 4001))
    image.save(large, format="PNG")
    image.close()
    animated = io.BytesIO()
    frames = [Image.new("RGB", (2, 2), color) for color in ("red", "blue")]
    frames[0].save(animated, format="PNG", save_all=True, append_images=frames[1:])
    for data in (large.getvalue(), animated.getvalue(), b"<svg onload='hostile()'/>"):
        assert (
            await client.post(
                "/api/v1/media", files={"file": ("upload", data, "image/png")}
            )
        ).status_code == 422

    async def chunks():
        for _ in range(11):
            yield b"x" * (1024 * 1024)

    assert (await client.post("/api/v1/media", content=chunks())).status_code == 422
    assert list(tmp_path.iterdir()) == []
