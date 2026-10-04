import pytest

from food_recommender.retrieval.embedding_contracts import (
    MINILM_MODEL,
    MINILM_REVISION,
    validate_query,
)


def test_query_requires_pinned_model_normalized_dimension_and_revision():
    validate_query((1.0,) + (0.0,) * 383, MINILM_MODEL, MINILM_REVISION)
    for vector, model, revision in [
        ((1.0,), MINILM_MODEL, MINILM_REVISION),
        ((0.0,) * 384, MINILM_MODEL, MINILM_REVISION),
        ((1.0,) + (0.0,) * 383, "clip", MINILM_REVISION),
        ((1.0,) + (0.0,) * 383, MINILM_MODEL, "main"),
    ]:
        with pytest.raises(ValueError):
            validate_query(vector, model, revision)
