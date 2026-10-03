"""Full-text updates and ordinary filter indexes, without approximate search."""

from sqlalchemy import insert, select, text, update
from test_provenance_models import document
from test_provenance_models import provenance as provenance

from food_recommender.infrastructure.provenance import Document


def test_full_text_is_derived_on_insert_and_update(provenance):
    provenance.execute(insert(Document), document(text="Roasted mushrooms and rice"))
    matching = select(Document.id).where(
        Document.search_vector.bool_op("@@")(
            text("plainto_tsquery('english', 'mushroom')")
        )
    )
    assert provenance.execute(matching).scalar_one() == "description"
    provenance.execute(update(Document).values(text="Fresh tomato soup"))
    assert provenance.execute(matching).all() == []
    assert (
        provenance.execute(
            select(Document.id).where(
                Document.search_vector.bool_op("@@")(
                    text("plainto_tsquery('english', 'tomatoes')")
                )
            )
        ).scalar_one()
        == "description"
    )


def test_required_filter_and_lexical_indexes_are_present(catalog):
    connection, _ = catalog
    definitions = connection.execute(
        text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'")
    ).all()
    indexes = dict(definitions)
    for name in (
        "ix_restaurants_filters",
        "ix_recipes_cuisine",
        "ix_reviews_profile_restaurant",
        "ix_documents_search",
        "ix_documents_source_record",
        "ix_source_records_restaurant",
        "ix_source_records_recipe",
        "ix_source_records_review",
        "ix_media_source_record",
    ):
        assert name in indexes
    assert "USING gin (search_vector)" in indexes["ix_documents_search"]
    assert "USING btree" in indexes["ix_restaurants_filters"]
    assert all(
        "USING hnsw" not in definition and "USING ivfflat" not in definition
        for definition in indexes.values()
    )
