"""Optional pretrained contract, provisioned before tests; never downloads."""

import os
from pathlib import Path

import pytest

from food_recommender.infrastructure.text_encoder import MiniLMEncoder


def test_pretrained_cpu_encoder_preserves_token_budget_and_semantics():
    root = os.environ.get("TEST_MINILM_ROOT")
    if not root:
        pytest.skip("Set TEST_MINILM_ROOT to explicitly provisioned pretrained weights")
    encoder = MiniLMEncoder(Path(root))
    vectors = encoder.encode(
        ("tomato basil pizza", "pizza with tomato and basil", "a diesel engine")
    )
    assert all(len(v) == 384 for v in vectors)

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(vectors[0], vectors[1]) > cosine(vectors[0], vectors[2])
    with pytest.raises(ValueError):
        encoder.encode(("rice " * 600,))
