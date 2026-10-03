import pytest
from test_image_index import Encoder, image_item
from test_ingestion_store import seed_store as seed_store

from food_recommender.domain.values import Category
from food_recommender.infrastructure.image_index import ImageIndexer
from food_recommender.infrastructure.image_search import PostgresImageSearch
from food_recommender.infrastructure.media import LocalMediaFiles
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
