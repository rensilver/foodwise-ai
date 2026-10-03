import pytest

from food_recommender.domain.values import Category
from food_recommender.infrastructure.clip_encoder import CLIP_MODEL, CLIP_REVISION
from food_recommender.retrieval.image_service import ImageRetrieval
from food_recommender.retrieval.models import TextPlan


class Encoder:
    model_id, revision = CLIP_MODEL, CLIP_REVISION

    def encode_texts(self, texts):
        assert texts == ("tomato soup",)
        return ((1.0,) + (0.0,) * 511,)


class Search:
    calls = []

    async def search(self, plan, category, vector, *, model, revision):
        self.calls.append((category, model, revision, len(vector)))
        return ()


@pytest.mark.asyncio
async def test_text_to_image_routes_matching_clip_query_to_each_category():
    search = Search()
    assert await ImageRetrieval(search, Encoder()).text(TextPlan("tomato soup")) == ()
    assert search.calls == [
        (c, CLIP_MODEL, CLIP_REVISION, 512)
        for c in (Category.RESTAURANT, Category.RECIPE)
    ]
