import pytest
from test_ingestion_store import seed_store as seed_store
from test_text_index import Encoder

from food_recommender.domain.values import Category
from food_recommender.infrastructure.persistence.indexing.text import TextIndexer
from food_recommender.infrastructure.persistence.search.text import PostgresTextSearch
from food_recommender.ingestion.adapters import (
    adapt_recipe,
    adapt_restaurant,
    adapt_review,
)
from food_recommender.ingestion.models import SeedItem
from food_recommender.ingestion.seed import artifact, source_record
from food_recommender.retrieval.models import TextPlan


async def populate(store, tmp_path):
    for category, adapter, payload, logical in [
        (
            "restaurant",
            adapt_restaurant,
            {
                "itemId": 1,
                "name": "Garden",
                "food_style": "Italian",
                "location": "LA",
                "price_range": 2,
                "vibe": "cozy pizza",
            },
            "r",
        ),
        (
            "restaurant",
            adapt_restaurant,
            {"itemId": 2, "name": "Garden Annex", "vibe": "cozy pizza"},
            "r",
        ),
        (
            "recipe",
            adapt_recipe,
            {
                "id": 1,
                "name": "Pizza",
                "cuisine": "Italian",
                "ingredients": ["cheese", "tomato"],
                "directions": ["bake pizza"],
            },
            "p",
        ),
        (
            "review",
            adapt_review,
            {"reviewId": 9, "itemId": 1, "userId": "demo-a", "text": "secret lavender"},
            "v",
        ),
        (
            "review",
            adapt_review,
            {
                "reviewId": 10,
                "itemId": 2,
                "userId": "demo-b",
                "text": "secret lavender",
            },
            "v",
        ),
    ]:
        path = tmp_path / logical
        path.write_text(logical)
        source = artifact(path, logical).source
        data = adapter(payload, logical).data
        record = source_record(source, category, data.id, raw=payload)
        await store.upsert(SeedItem(data, (source,), (record,), inputs=(payload,)))
    encoder = Encoder()
    await TextIndexer(store.sessions, encoder).build()
    return PostgresTextSearch(store.sessions), encoder


@pytest.mark.asyncio
async def test_both_branches_use_exact_applicable_metadata_and_real_citations(
    seed_store, tmp_path
):
    store, _ = seed_store
    search, encoder = await populate(store, tmp_path)
    plan = TextPlan("pizza", cuisine="Italian", location="LA", max_price_band=2)
    for branch in ("lexical", "dense"):
        for category in plan.categories:
            result = await search.search(
                plan, category, branch, encoder.encode(("pizza",))[0]
            )
            assert {hit.entity.id for hit in result} == {"1"}
            assert all(
                hit.citation.document_id and hit.citation.source_id for hit in result
            )
            if category == Category.RECIPE:
                assert result[0].ingredients == ("cheese", "tomato")
    assert (
        await search.search(
            TextPlan("pizza", location="unknown"), Category.RESTAURANT, "lexical"
        )
        == ()
    )


@pytest.mark.asyncio
async def test_review_scope_routes_to_actual_restaurant_and_exact_name(
    seed_store, tmp_path
):
    store, _ = seed_store
    search, _ = await populate(store, tmp_path)
    plan = TextPlan("lavender", sources=("review",), demo_profile_id="demo-a")
    hits = await search.search(plan, Category.RESTAURANT, "lexical")
    assert {h.entity.id for h in hits} == {"1"}
    assert all(h.source_type == "review" and h.citation.record_id == "9" for h in hits)
    assert await search.search(plan, Category.RECIPE, "lexical") == ()
    assert {
        h.entity.id
        for h in await search.search(
            TextPlan("pizza", name="Garden"), Category.RESTAURANT, "lexical"
        )
    } == {"1"}
    assert (
        await search.search(
            TextPlan("pizza' OR 1=1 --", entity_ids=("missing",)),
            Category.RESTAURANT,
            "lexical",
        )
        == ()
    )


@pytest.mark.asyncio
async def test_shared_retrieval_ranks_categories_separately_and_excludes_unknown_hard_constraints(
    seed_store, tmp_path
):
    from food_recommender.domain.preferences import Constraint
    from food_recommender.domain.values import ConstraintKind, Origin, Strength
    from food_recommender.retrieval.service import TextRetrieval

    store, _ = seed_store
    search, encoder = await populate(store, tmp_path)
    service = TextRetrieval(search, encoder)
    result = await service.retrieve(TextPlan("pizza", limit=1))
    assert len(result) == 2
    assert {r.evidence.entity.category for r in result} == {
        Category.RESTAURANT,
        Category.RECIPE,
    }
    assert all(r.evidence.citations and r.rrf_score > 0 for r in result)
    restricted = TextPlan(
        "pizza",
        constraints=(
            Constraint(ConstraintKind.ALLERGEN, "milk", Strength.HARD, Origin.EXPLICIT),
        ),
    )
    assert await service.retrieve(restricted) == ()


@pytest.mark.asyncio
async def test_missing_or_incompatible_stored_revision_is_dependency_error(
    seed_store, tmp_path
):
    from sqlalchemy import delete, update

    from food_recommender.infrastructure.persistence.models.embeddings import (
        TextEmbedding,
    )
    from food_recommender.retrieval.service import TextRetrieval

    store, connection = seed_store
    search, encoder = await populate(store, tmp_path)
    await connection.execute(update(TextEmbedding).values(revision="old-revision"))
    result = await TextRetrieval(search, encoder).run(TextPlan("pizza"))
    assert result.status == "dependency_error" and not result.candidates
    await connection.execute(delete(TextEmbedding))
    result = await TextRetrieval(search, encoder).run(TextPlan("pizza"))
    assert result.status == "dependency_error"


@pytest.mark.asyncio
async def test_no_matching_documents_is_empty_even_without_vectors(
    seed_store, tmp_path
):
    from food_recommender.retrieval.service import TextRetrieval

    store, _ = seed_store
    search, encoder = await populate(store, tmp_path)
    result = await TextRetrieval(search, encoder).run(
        TextPlan("pizza", entity_ids=("absent",))
    )
    assert result.status == "no_results"


@pytest.mark.asyncio
async def test_unindexed_catalog_is_unavailable_instead_of_a_genuine_empty_search(
    seed_store, tmp_path
):
    from sqlalchemy import delete

    from food_recommender.infrastructure.persistence.models.provenance import Document
    from food_recommender.retrieval.service import TextRetrieval

    store, connection = seed_store
    search, encoder = await populate(store, tmp_path)
    await connection.execute(delete(Document))
    result = await TextRetrieval(search, encoder).run(TextPlan("pizza"))
    assert result.status == "dependency_error"
    empty = await TextRetrieval(search, encoder).run(
        TextPlan("pizza", entity_ids=("missing",))
    )
    assert empty.status == "no_results"
