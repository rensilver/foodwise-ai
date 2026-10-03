import re

import pytest

from food_recommender.retrieval.chunking import chunks


def offsets(text):
    return tuple((m.start(), m.end()) for m in re.finditer(r"\S+", text))


def test_chunks_cover_unicode_source_and_late_ingredient_without_truncation():
    text = "café " * 700 + "peanut butter"
    result = chunks(text, offsets, max_tokens=254)
    assert len(result) == 3
    assert "".join(text[a:b] for a, b in result) == text
    assert "peanut butter" in text[slice(*result[-1])]
    assert all(len(offsets(text[a:b])) <= 254 for a, b in result)


def test_empty_and_invalid_token_boundaries():
    assert chunks("", offsets) == ()
    with pytest.raises(ValueError):
        chunks("hello", offsets, max_tokens=0)
    with pytest.raises(ValueError):
        chunks("hello", lambda _: ((0, 20),))
