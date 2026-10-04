from uuid import uuid4

import pytest
from sqlalchemy import insert
from test_image_index import image_item
from test_ingestion_store import seed_store as seed_store

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.persistence.models.context import BrowserSession
from food_recommender.infrastructure.persistence.models.provenance import Media
from food_recommender.infrastructure.persistence.query_media import AuthorizedQueryMedia


@pytest.mark.asyncio
async def test_query_media_enforces_session_or_explicit_catalog_scope(
    seed_store, tmp_path
):
    store, connection = seed_store
    media = await image_item(store, tmp_path)
    owner, stranger = uuid4(), uuid4()
    await connection.execute(
        insert(BrowserSession).values(id=owner, token_hash="a" * 64)
    )
    data = (tmp_path / media.storage_key).read_bytes()
    (tmp_path / "upload.png").write_bytes(data)
    await connection.execute(
        insert(Media).values(
            id="upload",
            owner_session_id=owner,
            storage_key="upload.png",
            mime_type="image/png",
            byte_size=len(data),
            width=32,
            height=32,
            content_hash=media.content_hash,
            ingestion_version="test",
            attribution="imported",
        )
    )
    resolver = AuthorizedQueryMedia(store.sessions, LocalMediaFiles(tmp_path))
    assert await resolver.read("upload", owner) == data
    for identifier, session_id in [
        ("upload", stranger),
        ("missing", owner),
        (media.id, owner),
        ("../upload.png", owner),
        ("https://example.com/x", owner),
    ]:
        with pytest.raises(ApplicationError) as error:
            await resolver.read(identifier, session_id)
        assert error.value.code in {ErrorCode.NOT_FOUND, ErrorCode.INVALID_REQUEST}
    assert await resolver.read(media.id, owner, allow_catalog=True) == data
    (tmp_path / "upload.png").unlink()
    (tmp_path / "upload.png").symlink_to(tmp_path / media.storage_key)
    with pytest.raises(ApplicationError):
        await resolver.read("upload", owner)


@pytest.mark.asyncio
async def test_image_to_image_service_resolves_only_authorized_ids(
    seed_store, tmp_path
):
    from test_image_index import Encoder

    from food_recommender.infrastructure.persistence.indexing.image import ImageIndexer
    from food_recommender.infrastructure.persistence.search.image import (
        PostgresImageSearch,
    )
    from food_recommender.retrieval.image_service import ImageRetrieval
    from food_recommender.retrieval.models import TextPlan

    store, _ = seed_store
    media = await image_item(store, tmp_path)
    await ImageIndexer(store.sessions, Encoder(), LocalMediaFiles(tmp_path)).build()
    service = ImageRetrieval(
        PostgresImageSearch(store.sessions),
        Encoder(),
        AuthorizedQueryMedia(store.sessions, LocalMediaFiles(tmp_path)),
        allow_catalog_queries=True,
    )
    hits = await service.image(TextPlan("image query"), media.id, uuid4())
    assert [(h.entity.id, h.media_id) for h in hits] == [("1", media.id)]
    with pytest.raises(ApplicationError):
        await service.image(
            TextPlan("image query"), str(tmp_path / media.storage_key), uuid4()
        )
