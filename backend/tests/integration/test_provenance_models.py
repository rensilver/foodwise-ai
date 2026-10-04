"""Source, document and media provenance contracts on migrated PostgreSQL."""

from datetime import UTC, datetime

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from food_recommender.infrastructure.persistence.models.base import Base
from food_recommender.infrastructure.persistence.models.catalog import (
    Recipe,
    Restaurant,
    Review,
)
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    Media,
    Source,
    SourceRecord,
)

HASH = "a" * 64
OBSERVED = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


def source(**changes: object) -> dict[str, object]:
    return {
        "id": "base-file",
        "logical_source_id": "course",
        "locator": "data/Recipes.json",
        "locator_kind": "file",
        "content_hash": HASH,
        "retrieved_at": OBSERVED,
        **changes,
    }


def record(**changes: object) -> dict[str, object]:
    return {
        "id": "recipe-record",
        "source_id": "base-file",
        "record_type": "recipe",
        "record_id": "1",
        "recipe_id": "1",
        "content_hash": HASH,
        "raw_payload": {"id": 1, "food_style": "Legacy", "ingredients": ["rice"]},
        "ingestion_version": "fixture-v1",
        "attribution": "imported",
        **changes,
    }


def document(**changes: object) -> dict[str, object]:
    return {
        "id": "description",
        "source_record_id": "recipe-record",
        "kind": "description",
        "text": "Original recipe description",
        "content_hash": HASH,
        "ingestion_version": "fixture-v1",
        "attribution": "source",
        **changes,
    }


def media(**changes: object) -> dict[str, object]:
    return {
        "id": "image",
        "source_record_id": "recipe-record",
        "storage_key": "fixture.png",
        "original_locator": "archive/recipe1.png",
        "mime_type": "image/png",
        "byte_size": 64,
        "width": 8,
        "height": 8,
        "content_hash": HASH,
        "ingestion_version": "fixture-v1",
        "attribution": "imported",
        **changes,
    }


@pytest.fixture
def provenance(catalog):
    connection, _ = catalog
    connection.execute(
        insert(Restaurant),
        {
            "id": "1",
            "source_id": "course",
            "source_record_id": "1",
            "name": "Place",
        },
    )
    connection.execute(
        insert(Recipe),
        {
            "id": "1",
            "source_id": "course",
            "source_record_id": "1",
            "name": "Dish",
        },
    )
    connection.execute(
        insert(Review),
        {
            "id": "1",
            "source_id": "course",
            "source_record_id": "1",
            "restaurant_id": "1",
            "demo_profile_id": "synthetic",
            "text": "Review",
        },
    )
    connection.execute(insert(Source), source())
    connection.execute(insert(SourceRecord), record())
    return connection


def test_raw_data_dates_hashes_and_attribution_roundtrip(provenance) -> None:
    connection = provenance
    connection.execute(insert(Media), media())
    connection.execute(
        insert(Document),
        document(
            id="caption",
            kind="image_caption",
            media_id="image",
            attribution="generated",
            generator="fixture-vision-model",
            generator_revision="r1",
            input_hash=HASH,
        ),
    )
    connection.execute(
        insert(Document),
        document(
            id="imported-caption",
            kind="image_caption",
            media_id="image",
            attribution="imported",
        ),
    )
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        artifact = session.get(Source, "base-file")
        original = session.get(SourceRecord, "recipe-record")
        generated = session.get(Document, "caption")
        imported = session.get(Document, "imported-caption")
        image = session.get(Media, "image")
        assert artifact.retrieved_at == OBSERVED
        assert artifact.published_on is None
        assert original.raw_payload == {
            "id": 1,
            "food_style": "Legacy",
            "ingredients": ["rice"],
        }
        assert original.raw_text is None
        assert original.generator is None
        assert generated.generator == "fixture-vision-model"
        assert generated.generator_revision == "r1"
        assert generated.input_hash == HASH
        assert imported.generator is None
        assert image.source_record_id == original.id
        assert image.original_locator == "archive/recipe1.png"
        assert (
            image.content_hash == original.content_hash == artifact.content_hash == HASH
        )
        for value in (artifact, original, generated, imported, image):
            assert value.created_at.utcoffset() is not None


def test_base_augmented_revisions_and_unresolved_records_preserve_identity(
    provenance,
) -> None:
    connection = provenance
    for artifact_id, locator, digest in (
        ("augmented", "data/augmented_food_recipe.json", HASH),
        ("base-revision", "data/Recipes.json", "b" * 64),
    ):
        connection.execute(
            insert(Source),
            {**source(), "id": artifact_id, "locator": locator, "content_hash": digest},
        )
        connection.execute(
            insert(SourceRecord), record(id=artifact_id, source_id=artifact_id)
        )
    connection.execute(
        insert(SourceRecord),
        record(
            id="unresolved",
            record_type="restaurant",
            record_id="paragraph-210",
            recipe_id=None,
            raw_payload=None,
            raw_text="  Original unstructured paragraph.\n",
        ),
    )
    assert connection.execute(select(Recipe.id)).scalars().all() == ["1"]
    assert connection.execute(
        select(SourceRecord.id).where(SourceRecord.recipe_id == "1")
    ).scalars().all() == ["recipe-record", "augmented", "base-revision"]
    assert (
        connection.execute(
            select(SourceRecord.raw_text).where(SourceRecord.id == "unresolved")
        ).scalar_one()
        == "  Original unstructured paragraph.\n"
    )


@pytest.mark.parametrize(
    "kind,field",
    [("restaurant", "restaurant_id"), ("recipe", "recipe_id"), ("review", "review_id")],
)
def test_each_record_type_links_to_its_real_catalog_entity(
    provenance, kind, field
) -> None:
    connection = provenance
    connection.execute(
        insert(SourceRecord),
        {
            **record(),
            "id": "linked",
            "record_id": "2",
            "record_type": kind,
            "recipe_id": None,
            field: "1",
        },
    )
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                update(SourceRecord)
                .where(SourceRecord.id == "linked")
                .values(**{field: "missing"})
            )
    assert (
        connection.execute(
            select(getattr(SourceRecord, field)).where(SourceRecord.id == "linked")
        ).scalar_one()
        == "1"
    )


@pytest.mark.parametrize(
    "model,factory,changes",
    [
        (Source, source, {"content_hash": "bad"}),
        (Source, source, {"locator_kind": "shell"}),
        (Source, source, {"logical_source_id": " "}),
        (Source, source, {"locator": " "}),
        (SourceRecord, record, {"source_id": "missing"}),
        (SourceRecord, record, {"record_type": "other"}),
        (SourceRecord, record, {"record_type": "restaurant"}),
        (SourceRecord, record, {"restaurant_id": "1"}),
        (SourceRecord, record, {"raw_payload": None}),
        (SourceRecord, record, {"content_hash": "A" * 64}),
        (SourceRecord, record, {"record_id": " "}),
        (SourceRecord, record, {"ingestion_version": ""}),
        (Document, document, {"source_record_id": "missing"}),
        (Document, document, {"attribution": "observed_ingredients"}),
        (Document, document, {"attribution": "generated"}),
        (Document, document, {"attribution": "generated", "generator": "model"}),
        (Document, document, {"attribution": "generated", "input_hash": HASH}),
        (Document, document, {"input_hash": "invalid"}),
        (
            Document,
            document,
            {
                "attribution": "generated",
                "generator": "model",
                "input_hash": HASH,
                "generator_revision": " ",
            },
        ),
        (Document, document, {"text": " "}),
        (Document, document, {"content_hash": "b" * 63}),
        (Document, document, {"start_offset": 0}),
        (Document, document, {"start_offset": 5, "end_offset": 3}),
        (Document, document, {"start_offset": -1, "end_offset": 3}),
        (Media, media, {"source_record_id": "missing"}),
        (Media, media, {"storage_key": "../private.png"}),
        (Media, media, {"storage_key": "/private.png"}),
        (Media, media, {"original_locator": " "}),
        (Media, media, {"mime_type": "image/svg+xml"}),
        (Media, media, {"width": 0}),
        (Media, media, {"height": -1}),
        (Media, media, {"byte_size": 0}),
    ],
)
def test_invalid_provenance_is_rejected_without_losing_records(
    provenance, model, factory, changes
) -> None:
    connection = provenance
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            payload = {**factory(), "id": "invalid", **changes}
            if model is Source:
                payload["locator"] = changes.get("locator", "data/Other.json")
            elif model is SourceRecord:
                payload["record_id"] = changes.get("record_id", "other")
            connection.execute(insert(model), payload)
    assert connection.execute(select(SourceRecord.id)).scalars().all() == [
        "recipe-record"
    ]


@pytest.mark.parametrize("model,factory", [(Source, source), (SourceRecord, record)])
@pytest.mark.parametrize("duplicate", ["id", "source_identity"])
def test_duplicate_source_identity_is_rejected(
    provenance, model, factory, duplicate
) -> None:
    payload = factory()
    if duplicate == "source_identity":
        payload["id"] = "duplicate"
    elif model is Source:
        payload["locator"] = "data/Other.json"
    else:
        payload["record_id"] = "other"
    with pytest.raises(IntegrityError):
        with provenance.begin_nested():
            provenance.execute(insert(model), payload)


def test_record_type_namespaces_and_document_offsets(provenance) -> None:
    provenance.execute(
        insert(SourceRecord),
        record(
            id="place-record",
            record_type="restaurant",
            recipe_id=None,
            restaurant_id="1",
        ),
    )
    provenance.execute(insert(Document), document(start_offset=0, end_offset=27))
    assert provenance.execute(
        select(Document.start_offset, Document.end_offset)
    ).one() == (0, 27)
    assert set(provenance.execute(select(SourceRecord.record_type)).scalars()) == {
        "restaurant",
        "recipe",
    }


def test_url_source_publication_and_retrieval_dates(provenance) -> None:
    provenance.execute(
        insert(Source),
        source(
            id="url",
            locator_kind="url",
            locator="https://example.test/catalog",
            published_on=OBSERVED.date(),
        ),
    )
    row = provenance.execute(
        select(Source.published_on, Source.retrieved_at).where(Source.id == "url")
    ).one()
    assert row == (OBSERVED.date(), OBSERVED)


def test_media_keys_are_unique_but_identical_content_can_have_distinct_associations(
    provenance,
) -> None:
    connection = provenance
    connection.execute(insert(Media), media())
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(Media), media(id="duplicate"))
    connection.execute(
        insert(SourceRecord),
        record(id="review-record", record_type="review", recipe_id=None, review_id="1"),
    )
    connection.execute(
        insert(Media),
        media(
            id="review-image",
            source_record_id="review-record",
            storage_key="review.png",
        ),
    )
    assert connection.execute(select(Media.content_hash)).scalars().all() == [
        HASH,
        HASH,
    ]
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(Document),
                document(media_id="review-image", kind="image_caption"),
            )


@pytest.mark.parametrize("model", [Source, SourceRecord, Recipe, Media])
def test_provenance_parent_deletion_and_id_changes_are_restricted(
    provenance, model
) -> None:
    connection = provenance
    connection.execute(insert(Media), media())
    connection.execute(insert(Document), document(media_id="image"))
    for statement in (delete(model), update(model).values(id="renamed")):
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(statement)
    assert connection.execute(select(Document.id)).scalar_one() == "description"


def test_partial_document_media_write_rolls_back(provenance) -> None:
    connection = provenance
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(Media), media())
            connection.execute(insert(Document), document(media_id="missing"))
    assert connection.execute(select(Media.id)).scalars().all() == []
    assert connection.execute(select(Document.id)).scalars().all() == []


def test_upgrade_preserves_catalog_and_downgrade_removes_only_provenance(
    catalog,
) -> None:
    connection, config = catalog
    command.downgrade(config, "0001_catalog")
    connection.execute(
        insert(Recipe),
        {
            "id": "1",
            "source_id": "course",
            "source_record_id": "1",
            "name": "Preserved dish",
        },
    )
    command.upgrade(config, "head")
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    connection.execute(insert(Source), source())
    connection.execute(insert(SourceRecord), record())
    connection.execute(insert(Media), media())
    connection.execute(insert(Document), document(media_id="image"))
    command.downgrade(config, "0001_catalog")
    for name in ("sources", "source_records", "documents", "media"):
        assert (
            connection.exec_driver_sql("SELECT to_regclass(%s)", (name,)).scalar_one()
            is None
        )
    assert connection.execute(select(Recipe.name)).scalar_one() == "Preserved dish"
    command.upgrade(config, "head")
    assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
