"""Separate model-compatible vector storage on migrated PostgreSQL."""

import pytest
from sqlalchemy import delete, insert, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, StatementError
from test_provenance_models import HASH, document, media
from test_provenance_models import provenance as provenance

from food_recommender.infrastructure.embeddings import ImageEmbedding, TextEmbedding
from food_recommender.infrastructure.provenance import Document, Media


def embedding(**changes):
    return dict(
        id="vector",
        model="sentence-transformers/all-MiniLM-L6-v2",
        revision="fixture-r1",
        input_hash=HASH,
        dimension=384,
        document_id="description",
        embedding=[1.0] + [0.0] * 383,
        **changes,
    )


def test_text_and_image_roundtrip_exact_cosine_and_provenance(provenance):
    provenance.execute(insert(Document), document())
    provenance.execute(insert(Media), media())
    provenance.execute(insert(TextEmbedding), embedding())
    second = embedding()
    second.update(
        id="vector2", revision="fixture-r2", embedding=[0.0, 1.0] + [0.0] * 382
    )
    provenance.execute(insert(TextEmbedding), second)
    provenance.execute(
        insert(ImageEmbedding),
        dict(
            id="image-vector",
            media_id="image",
            model="openai/clip-vit-base-patch32",
            revision="fixture-r1",
            input_hash=HASH,
            dimension=512,
            embedding=[1.0] + [0.0] * 511,
        ),
    )
    query = [1.0] + [0.0] * 383
    assert provenance.execute(
        select(TextEmbedding.id).order_by(
            TextEmbedding.embedding.cosine_distance(query), TextEmbedding.id
        )
    ).scalars().all() == ["vector", "vector2"]
    assert len(provenance.execute(select(ImageEmbedding.embedding)).scalar_one()) == 512
    provenance.execute(delete(Document))
    assert provenance.execute(select(TextEmbedding.id)).all() == []
    assert provenance.execute(select(ImageEmbedding.id)).scalar_one() == "image-vector"


@pytest.mark.parametrize(
    "changes",
    [
        dict(model="clip"),
        dict(revision=" "),
        dict(input_hash="bad"),
        dict(dimension=512),
        dict(document_id="missing"),
        dict(embedding=[0.0] * 384),
        dict(embedding=[2.0] + [0.0] * 383),
    ],
)
def test_incompatible_metadata_and_non_normalized_vectors_rejected(provenance, changes):
    provenance.execute(insert(Document), document())
    payload = embedding()
    payload.update(changes)
    with pytest.raises(IntegrityError):
        with provenance.begin_nested():
            provenance.execute(insert(TextEmbedding), payload)


def test_wrong_dimensions_and_duplicate_model_revision_rejected(provenance):
    provenance.execute(insert(Document), document())
    payload = embedding()
    payload["embedding"] = [1.0, 0.0]
    with pytest.raises(StatementError):
        with provenance.begin_nested():
            provenance.execute(insert(TextEmbedding), payload)
    provenance.execute(insert(TextEmbedding), embedding())
    payload = embedding()
    payload["id"] = "duplicate"
    with pytest.raises(IntegrityError):
        with provenance.begin_nested():
            provenance.execute(insert(TextEmbedding), payload)
    with pytest.raises(DBAPIError):
        with provenance.begin_nested():
            provenance.execute(text("UPDATE text_embeddings SET embedding = '[1,0]'"))
