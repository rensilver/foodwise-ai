import pytest
from test_image_index import Encoder, image_item
from test_ingestion_store import seed_store as seed_store

from food_recommender.domain.values import Category
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.persistence.indexing.image import ImageIndexer
from food_recommender.infrastructure.persistence.search.image import PostgresImageSearch
from food_recommender.retrieval.models import TextPlan


@pytest.mark.asyncio
async def test_clip_cosine_search_filters_and_matches_actual_media(
    seed_store, tmp_path
):
    store, _ = seed_store
    media = await image_item(store, tmp_path)
    await ImageIndexer(store.sessions, Encoder(), LocalMediaFiles(tmp_path)).build()
    search = PostgresImageSearch(store.sessions)
    vector = Encoder().encode_images((b"fixture",))[0]
    hits = await search.search(
        TextPlan("tomato", cuisine="Italian", location="LA"),
        Category.RECIPE,
        vector,
        model=Encoder.model_id,
        revision=Encoder.revision,
    )
    assert len(hits) == 1
    assert hits[0].entity.id == "1" and hits[0].media_id == media.id
    assert hits[0].cosine_similarity == pytest.approx(1)
    assert hits[0].citation.document_id == f"image:{media.id}"
    assert (
        await search.search(
            TextPlan("tomato", entity_ids=("absent",)),
            Category.RECIPE,
            vector,
            model=Encoder.model_id,
            revision=Encoder.revision,
        )
        == ()
    )
    with pytest.raises(ValueError):
        await search.search(
            TextPlan("tomato"),
            Category.RECIPE,
            vector[:384],
            model=Encoder.model_id,
            revision=Encoder.revision,
        )
    with pytest.raises(ValueError):
        await search.search(
            TextPlan("tomato"),
            Category.RECIPE,
            vector,
            model=Encoder.model_id,
            revision="wrong",
        )


@pytest.mark.asyncio
async def test_review_images_are_scoped_to_profile_and_actual_restaurant(
    seed_store, tmp_path
):
    import hashlib
    import io

    from PIL import Image
    from sqlalchemy import insert, select
    from test_text_search import populate

    from food_recommender.infrastructure.persistence.models.provenance import (
        Media,
        SourceRecord,
    )

    store, connection = seed_store
    await populate(store, tmp_path)
    for review in ("9", "10"):
        buffer = io.BytesIO()
        Image.new("RGB", (32, 32), "red" if review == "9" else "blue").save(
            buffer, format="PNG"
        )
        data = buffer.getvalue()
        key = f"review{review}.png"
        (tmp_path / key).write_bytes(data)
        record_id = (
            await connection.execute(
                select(SourceRecord.id).where(SourceRecord.review_id == review)
            )
        ).scalar_one()
        await connection.execute(
            insert(Media).values(
                id=f"review{review}",
                source_record_id=record_id,
                storage_key=key,
                mime_type="image/png",
                byte_size=len(data),
                width=32,
                height=32,
                content_hash=hashlib.sha256(data).hexdigest(),
                ingestion_version="test",
                attribution="imported",
            )
        )
    await ImageIndexer(store.sessions, Encoder(), LocalMediaFiles(tmp_path)).build()
    search = PostgresImageSearch(store.sessions)
    plan = TextPlan("lavender", sources=("review",), demo_profile_id="demo-a")
    vector = Encoder().encode_images((b"fixture",))[0]
    hits = await search.search(
        plan,
        Category.RESTAURANT,
        vector,
        model=Encoder.model_id,
        revision=Encoder.revision,
    )
    assert [(h.entity.id, h.media_id, h.citation.record_id) for h in hits] == [
        ("1", "review9", "9")
    ]
    assert (
        await search.search(
            plan,
            Category.RECIPE,
            vector,
            model=Encoder.model_id,
            revision=Encoder.revision,
        )
        == ()
    )
    assert (
        await search.search(
            TextPlan(
                "lavender",
                sources=("review",),
                demo_profile_id="demo-a",
                location="missing",
            ),
            Category.RESTAURANT,
            vector,
            model=Encoder.model_id,
            revision=Encoder.revision,
        )
        == ()
    )
