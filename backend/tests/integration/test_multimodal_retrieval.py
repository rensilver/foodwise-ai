import pytest
from test_image_index import Encoder, image_item
from test_ingestion_store import seed_store as seed_store
from test_text_search import populate

from food_recommender.domain.values import Category
from food_recommender.infrastructure.image_index import ImageIndexer
from food_recommender.infrastructure.image_search import PostgresImageSearch
from food_recommender.infrastructure.media import LocalMediaFiles
from food_recommender.infrastructure.text_index import TextIndexer
from food_recommender.retrieval.image_service import ImageRetrieval
from food_recommender.retrieval.models import TextPlan
from food_recommender.retrieval.multimodal import MultimodalRetrieval
from food_recommender.retrieval.service import TextRetrieval


class CLIP(Encoder):
    def encode_texts(self, texts):
        return self.encode_images(tuple(t.encode() for t in texts))


@pytest.mark.asyncio
async def test_categories_rank_separately_and_recipe_images_never_leak_to_same_id_restaurant(
    seed_store, tmp_path
):
    store, _ = seed_store
    search, text_encoder = await populate(store, tmp_path)
    media = await image_item(store, tmp_path, identity="3")
    await image_item(store, tmp_path, identity="1", color="blue")
    await TextIndexer(store.sessions, text_encoder).build()
    await ImageIndexer(store.sessions, CLIP(), LocalMediaFiles(tmp_path)).build()
    # Recipe 1 shares an ID with restaurant 1; imagery must remain recipe evidence.
    service = MultimodalRetrieval(
        TextRetrieval(search, text_encoder),
        ImageRetrieval(PostgresImageSearch(store.sessions), CLIP()),
    )
    result = await service.run(TextPlan("pizza", limit=2))
    assert result.status == "success"
    restaurants = [
        c
        for c in result.candidates
        if c.evidence.entity.category == Category.RESTAURANT
    ]
    recipes = [
        c for c in result.candidates if c.evidence.entity.category == Category.RECIPE
    ]
    assert len(restaurants) == len(recipes) == 2
    assert all(
        c.media_ids == () and c.evidence.image_score is None for c in restaurants
    )
    assert any(media.id in c.media_ids for c in recipes)
    assert all(
        citation.entity == c.evidence.entity
        for c in result.candidates
        for citation in c.evidence.citations
    )
    assert result.categories[0].fusion.text_weight == 1
