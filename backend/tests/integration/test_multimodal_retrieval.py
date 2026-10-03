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


@pytest.mark.asyncio
async def test_image_only_combined_queries_exact_filters_and_hard_constraints(
    seed_store, tmp_path
):
    from uuid import uuid4

    from food_recommender.domain.preferences import Constraint
    from food_recommender.domain.values import ConstraintKind, Origin, Strength
    from food_recommender.infrastructure.query_media import AuthorizedQueryMedia

    store, _ = seed_store
    search, text_encoder = await populate(store, tmp_path)
    media = await image_item(store, tmp_path, identity="3")
    await TextIndexer(store.sessions, text_encoder).build()
    await ImageIndexer(store.sessions, CLIP(), LocalMediaFiles(tmp_path)).build()
    images = ImageRetrieval(
        PostgresImageSearch(store.sessions),
        CLIP(),
        AuthorizedQueryMedia(store.sessions, LocalMediaFiles(tmp_path)),
        allow_catalog_queries=True,
    )
    service = MultimodalRetrieval(TextRetrieval(search, text_encoder), images)
    image_only = await service.run(
        TextPlan("image query"), media_id=media.id, session_id=uuid4(), use_text=False
    )
    assert image_only.status == "success"
    assert [
        (c.evidence.entity.category, c.evidence.entity.id)
        for c in image_only.candidates
    ] == [(Category.RECIPE, "3")]
    combined = await service.run(
        TextPlan("pizza", cuisine="Italian", location="LA", entity_ids=("3",)),
        media_id=media.id,
        session_id=uuid4(),
    )
    assert combined.status == "success" and len(combined.candidates) == 1
    assert (
        combined.candidates[0].evidence.text_score
        == combined.candidates[0].evidence.image_score
        == 1
    )
    empty = await service.run(TextPlan("pizza", cuisine="unknown"))
    assert empty.status == "no_results"
    restricted = await service.run(
        TextPlan(
            "pizza",
            constraints=(
                Constraint(
                    ConstraintKind.ALLERGEN, "milk", Strength.HARD, Origin.EXPLICIT
                ),
            ),
        )
    )
    # Even plant-only recipes have unknown allergen absence/cross-contact evidence.
    assert restricted.status == "no_results" and not restricted.candidates
    vegan = await service.run(
        TextPlan(
            "pizza",
            constraints=(
                Constraint(
                    ConstraintKind.DIETARY, "vegan", Strength.HARD, Origin.EXPLICIT
                ),
            ),
        )
    )
    assert vegan.status == "success"
    assert [c.evidence.entity.id for c in vegan.candidates] == ["3"]
    assert all(
        a.state.value == "supported" for c in vegan.candidates for a in c.assessments
    )


@pytest.mark.asyncio
async def test_missing_stale_and_partial_image_vectors_report_degradation(
    seed_store, tmp_path
):
    from sqlalchemy import update

    from food_recommender.infrastructure.embeddings import ImageEmbedding

    store, connection = seed_store
    search, encoder = await populate(store, tmp_path)
    await image_item(store, tmp_path, identity="3")
    await TextIndexer(store.sessions, encoder).build()
    await ImageIndexer(store.sessions, CLIP(), LocalMediaFiles(tmp_path)).build()
    service = MultimodalRetrieval(
        TextRetrieval(search, encoder),
        ImageRetrieval(PostgresImageSearch(store.sessions), CLIP()),
    )
    good = await service.run(TextPlan("pizza"))
    assert good.status == "success"
    assert any(
        c.evidence.image_score == 0
        for c in good.candidates
        if c.evidence.entity.category == Category.RECIPE
    )
    await connection.execute(update(ImageEmbedding).values(revision="stale"))
    degraded = await service.run(TextPlan("pizza"))
    assert (
        degraded.status == "success"
        and "Image dependency unavailable" in degraded.limitations
    )
    assert all(c.evidence.image_score is None for c in degraded.candidates)
    broken_image_only = await service.run(TextPlan("pizza"), use_text=False)
    assert broken_image_only.status == "dependency_error"
