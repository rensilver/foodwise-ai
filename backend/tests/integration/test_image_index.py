import hashlib
import io

import pytest
from PIL import Image
from sqlalchemy import select
from test_ingestion_store import seed_store as seed_store

from food_recommender.domain.catalog import MediaData
from food_recommender.infrastructure.clip_encoder import CLIP_MODEL, CLIP_REVISION
from food_recommender.infrastructure.embeddings import ImageEmbedding
from food_recommender.infrastructure.image_index import ImageIndexer
from food_recommender.infrastructure.media import LocalMediaFiles
from food_recommender.ingestion.adapters import adapt_recipe
from food_recommender.ingestion.models import SeedItem
from food_recommender.ingestion.seed import artifact, caption_document, source_record


class Encoder:
    model_id, revision = CLIP_MODEL, CLIP_REVISION
    calls = 0

    def encode_images(self, images):
        self.calls += len(images)
        return tuple((1.0,) + (0.0,) * 511 for _ in images)


async def image_item(store, tmp_path, identity="1", color="red"):
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(buffer, format="PNG")
    data = buffer.getvalue()
    key = f"image{identity}.png"
    path = tmp_path / key
    path.write_bytes(data)
    payload = {
        "id": int(identity),
        "name": f"Soup {identity}",
        "cuisine": "Italian",
        "ingredients": ["tomato"],
        "directions": ["simmer"],
    }
    source = artifact(path, "images").source
    record = source_record(source, "recipe", identity, raw=payload)
    media = MediaData(
        id=f"media{identity}",
        source_record_id=record["id"],
        storage_key=key,
        mime_type="image/png",
        byte_size=len(data),
        width=32,
        height=32,
        content_hash=hashlib.sha256(data).hexdigest(),
        ingestion_version="test",
        attribution="imported",
    )
    caption = caption_document(record, "Red tomato soup", media_id=media.id)
    await store.upsert(
        SeedItem(
            adapt_recipe(payload, "recipes").data,
            (source,),
            (record,),
            (caption,),
            (media,),
            inputs=(payload,),
        )
    )
    return media


@pytest.mark.asyncio
async def test_index_checks_hash_links_and_skips_unchanged_inference(
    seed_store, tmp_path
):
    store, connection = seed_store
    media = await image_item(store, tmp_path)
    encoder = Encoder()
    indexer = ImageIndexer(store.sessions, encoder, LocalMediaFiles(tmp_path))
    assert await indexer.build() == {"media": 1, "embedded": 1, "unchanged": 0}
    assert await indexer.build() == {"media": 1, "embedded": 0, "unchanged": 1}
    assert encoder.calls == 1
    row = (
        await connection.execute(
            select(ImageEmbedding.media_id, ImageEmbedding.dimension)
        )
    ).one()
    assert row == (media.id, 512)
    (tmp_path / media.storage_key).write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        await indexer.build()


@pytest.mark.asyncio
async def test_invalid_encoder_batch_does_not_commit(seed_store, tmp_path):
    store, connection = seed_store
    await image_item(store, tmp_path)

    class Bad(Encoder):
        def encode_images(self, images):
            return ((0.0,) * 512,)

    with pytest.raises(ValueError):
        await ImageIndexer(store.sessions, Bad(), LocalMediaFiles(tmp_path)).build()
    assert (await connection.execute(select(ImageEmbedding.id))).all() == []
