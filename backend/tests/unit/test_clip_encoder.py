import pytest

from food_recommender.retrieval.embedding_contracts import (
    CLIP_MODEL,
    CLIP_REVISION,
    validate_clip,
)


def test_clip_rejects_incompatible_nonfinite_unnormalized_queries():
    vector = (1.0,) + (0.0,) * 511
    validate_clip(vector, CLIP_MODEL, CLIP_REVISION)
    for values, model, revision in [
        (vector[:384], CLIP_MODEL, CLIP_REVISION),
        (vector, CLIP_MODEL, "different"),
        (vector, "sentence-transformers/all-MiniLM-L6-v2", CLIP_REVISION),
        ((float("nan"),) + vector[1:], CLIP_MODEL, CLIP_REVISION),
        ((0.0,) * 512, CLIP_MODEL, CLIP_REVISION),
    ]:
        with pytest.raises(ValueError):
            validate_clip(values, model, revision)
