"""Reject incompatible prepared inputs before opening a write transaction."""

import hashlib
from dataclasses import replace

import pytest

from food_recommender.domain.catalog import (
    DocumentData,
    EmbeddingData,
    PreparedCatalog,
    RecipeData,
    RecordData,
    SourceData,
)


def prepared():
    digest = hashlib.sha256(b"Rice").hexdigest()
    common = dict(ingestion_version="v1", attribution="source")
    return PreparedCatalog(
        RecipeData(id="1", source_id="course", source_record_id="1", name="Rice"),
        sources=(
            SourceData(
                id="file",
                logical_source_id="course",
                locator_kind="file",
                locator="data/fixture.json",
                content_hash=digest,
            ),
        ),
        records=(
            RecordData(
                id="raw",
                source_id="file",
                record_id="1",
                record_type="recipe",
                raw_text="Rice",
                content_hash=digest,
                **common,
            ),
        ),
        documents=(
            DocumentData(
                id="doc",
                source_record_id="raw",
                kind="description",
                text="Rice",
                content_hash=digest,
                **common,
            ),
        ),
        text_embeddings=(
            EmbeddingData(
                id="vector",
                parent_id="doc",
                model="sentence-transformers/all-MiniLM-L6-v2",
                revision="r1",
                input_hash=digest,
                values=(1.0,) + (0.0,) * 383,
            ),
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        "wrong_hash",
        "wrong_source",
        "wrong_parent",
        "wrong_modality",
        "duplicate",
        "wrong_dimensions",
        "nan",
    ],
)
def test_prepared_bundle_rejects_unsafe_content(change):
    value = prepared()
    with pytest.raises(ValueError):
        if change == "wrong_hash":
            replace(value.documents[0], content_hash="b" * 64)
        elif change == "wrong_source":
            replace(value, records=(replace(value.records[0], source_id="missing"),))
        elif change == "wrong_parent":
            replace(
                value,
                text_embeddings=(
                    replace(value.text_embeddings[0], parent_id="missing"),
                ),
            )
        elif change == "wrong_modality":
            replace(value, image_embeddings=value.text_embeddings)
        elif change == "duplicate":
            replace(value, documents=value.documents * 2)
        elif change == "wrong_dimensions":
            replace(value.text_embeddings[0], values=(1.0,))
        else:
            replace(value.text_embeddings[0], values=(float("nan"),) + (0.0,) * 383)
