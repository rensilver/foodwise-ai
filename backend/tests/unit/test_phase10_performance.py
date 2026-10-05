"""Performance summaries preserve sample counts."""

from scripts.measure_phase10_performance import summarize


def test_summary_uses_nearest_rank():
    assert summarize([1, 2, 3, 4, 100]) == {
        "samples": 5,
        "p50_ms": 3,
        "p95_ms": 100,
        "minimum_ms": 1,
        "maximum_ms": 100,
    }
