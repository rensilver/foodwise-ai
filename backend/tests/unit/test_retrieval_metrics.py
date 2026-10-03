import math

import pytest

from food_recommender.retrieval.metrics import ndcg, recall


def test_metrics_penalize_missed_and_late_targets_without_duplicate_credit():
    assert recall(("a", "b", "a"), {"a", "c"}, 20) == 0.5
    assert ndcg(("a", "b"), {"a"}, 5) == 1
    assert ndcg(("b", "a"), {"a"}, 5) == pytest.approx(1 / math.log2(3))
    assert recall((), {"a"}, 20) == 0
    assert ndcg(("b",), {"a"}, 5) == 0
    assert ndcg(("a", "a"), {"a", "b"}, 5) < 1
    assert recall((), set(), 20) is None
    assert ndcg((), set(), 5) is None
