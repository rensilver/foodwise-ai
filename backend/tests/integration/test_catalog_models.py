"""Catalog identity and integrity enforced by migrated, real PostgreSQL tables."""

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from food_recommender.infrastructure.catalog import Base, Recipe, Restaurant, Review


def restaurant(**changes: object) -> dict[str, object]:
    return {
        "id": "1",
        "source_id": "course",
        "source_record_id": "1",
        "name": "Fixture restaurant",
        **changes,
    }


def recipe(**changes: object) -> dict[str, object]:
    return {
        "id": "1",
        "source_id": "course",
        "source_record_id": "1",
        "name": "Fixture recipe",
        **changes,
    }


def review(**changes: object) -> dict[str, object]:
    return {
        "id": "1",
        "source_id": "course",
        "source_record_id": "1",
        "restaurant_id": "1",
        "demo_profile_id": "synthetic-profile",
        "text": "Fixture review",
        **changes,
    }


def test_fresh_migration_matches_models_and_is_reversible(catalog) -> None:
    connection, config = catalog
    assert set(Base.metadata.tables) == {
        "restaurants",
        "recipes",
        "reviews",
        "sources",
        "source_records",
        "documents",
        "media",
        "text_embeddings",
        "image_embeddings",
    }
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    assert (
        connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
        == "0003_embeddings"
    )
    command.downgrade(config, "base")
    assert (
        connection.exec_driver_sql("SELECT to_regclass('restaurants')").scalar_one()
        is None
    )
    assert (
        connection.exec_driver_sql("SELECT to_regclass('recipes')").scalar_one() is None
    )
    assert (
        connection.exec_driver_sql("SELECT to_regclass('reviews')").scalar_one() is None
    )
    command.upgrade(config, "head")
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_stable_ids_and_type_source_namespaces(catalog) -> None:
    connection, _ = catalog
    connection.execute(insert(Restaurant), restaurant())
    connection.execute(insert(Recipe), recipe())
    connection.execute(insert(Review), review())
    connection.execute(
        insert(Restaurant), restaurant(id="other-source:1", source_id="other-source")
    )
    connection.execute(
        update(Restaurant).where(Restaurant.id == "1").values(name="Updated fixture")
    )
    assert connection.execute(
        select(Restaurant.id).order_by(Restaurant.id)
    ).scalars().all() == ["1", "other-source:1"]
    assert connection.execute(select(Recipe.id)).scalar_one() == "1"
    assert connection.execute(select(Review.restaurant_id)).scalar_one() == "1"


@pytest.mark.parametrize(
    "model,factory", [(Restaurant, restaurant), (Recipe, recipe), (Review, review)]
)
@pytest.mark.parametrize("duplicate", ["canonical", "source"])
def test_duplicate_identity_is_rejected_without_losing_existing_rows(
    catalog, model, factory, duplicate
) -> None:
    connection, _ = catalog
    if model is Review:
        connection.execute(insert(Restaurant), restaurant())
    connection.execute(insert(model), factory())
    changes = {"id": "2"} if duplicate == "source" else {"source_record_id": "2"}
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(model), factory(**changes))
    assert connection.execute(select(model.id)).scalars().all() == ["1"]


@pytest.mark.parametrize("operation", ["insert", "update", "delete", "rename_parent"])
def test_review_foreign_key_is_enforced(catalog, operation) -> None:
    connection, _ = catalog
    connection.execute(insert(Restaurant), restaurant())
    connection.execute(insert(Recipe), recipe(id="recipe-only"))
    connection.execute(insert(Review), review())
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            if operation == "insert":
                connection.execute(
                    insert(Review),
                    review(id="2", source_record_id="2", restaurant_id="recipe-only"),
                )
            elif operation == "update":
                connection.execute(update(Review).values(restaurant_id="missing"))
            elif operation == "delete":
                connection.execute(delete(Restaurant))
            else:
                connection.execute(update(Restaurant).values(id="renamed"))
    assert connection.execute(select(Review.restaurant_id)).scalar_one() == "1"


def test_optional_metadata_remains_unknown_and_collections_roundtrip(catalog) -> None:
    connection, _ = catalog
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        place = Restaurant(**restaurant())
        dish = Recipe(**recipe())
        session.add_all([place, dish])
        session.flush()
        feedback = Review(**review())
        session.add(feedback)
        session.flush()
        session.expire_all()
        assert (
            connection.execute(
                select(Recipe.id).where(Recipe.nutrition.is_(None))
            ).scalar_one()
            == "1"
        )
        for field in (
            "cuisine",
            "normalized_cuisine",
            "location",
            "normalized_location",
            "restaurant_type",
            "rating",
            "price_band",
            "signatures",
            "vibe",
            "environment",
            "shortcomings",
            "availability",
            "latitude",
            "longitude",
            "allergens",
        ):
            assert getattr(place, field) is None
        for field in (
            "cuisine",
            "normalized_cuisine",
            "servings",
            "prep_time",
            "cook_time",
            "total_time",
            "ingredients",
            "directions",
            "difficulty",
            "nutrition",
            "availability",
            "allergens",
        ):
            assert getattr(dish, field) is None
        for field in ("title", "rating", "published_on", "language"):
            assert getattr(feedback, field) is None
        dish.ingredients = ["rice", "peas"]
        dish.directions = ["Rinse rice.", "Cook with peas."]
        dish.prep_time = "10 mins"
        dish.allergens = []
        place.cuisine = "Legacy Food Style"
        place.normalized_cuisine = "legacy food style"
        session.flush()
        session.expire_all()
        assert dish.ingredients == ["rice", "peas"]
        assert dish.directions == ["Rinse rice.", "Cook with peas."]
        assert dish.prep_time == "10 mins"
        assert dish.allergens == []
        assert place.cuisine == "Legacy Food Style"
        assert place.normalized_cuisine == "legacy food style"
        dish.nutrition = {"source_note": "Synthetic test metadata"}
        session.flush()
        dish.nutrition = None
        session.flush()
        assert (
            connection.execute(
                select(Recipe.id).where(Recipe.nutrition.is_(None))
            ).scalar_one()
            == "1"
        )


@pytest.mark.parametrize(
    "model,factory,field,value",
    [
        (Restaurant, restaurant, "id", " "),
        (Restaurant, restaurant, "source_id", "\t\n"),
        (Recipe, recipe, "source_id", ""),
        (Recipe, recipe, "source_record_id", None),
        (Review, review, "source_record_id", " "),
        (Restaurant, restaurant, "name", ""),
        (Recipe, recipe, "name", " "),
        (Review, review, "demo_profile_id", ""),
        (Review, review, "text", " "),
        (Restaurant, restaurant, "price_band", 0),
        (Restaurant, restaurant, "price_band", 5),
        (Restaurant, restaurant, "rating", 5.1),
        (Review, review, "rating", -1),
        (Restaurant, restaurant, "latitude", 91),
        (Restaurant, restaurant, "longitude", -181),
        (Recipe, recipe, "servings", 0),
    ],
)
def test_invalid_catalog_values_are_rejected_by_database(
    catalog, model, factory, field, value
) -> None:
    connection, _ = catalog
    if model is Review:
        connection.execute(insert(Restaurant), restaurant())
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(model), factory(**{field: value}))


def test_new_ids_are_explicit_and_never_derived_from_row_count(catalog) -> None:
    connection, _ = catalog
    payload = restaurant()
    payload["id"] = None
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(Restaurant), payload)
