"""Binary relevance metrics over explicit source-backed labels, not model opinions."""

import math


def recall(ranked: tuple[str, ...], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    return len(set(ranked[:k]) & relevant) / len(relevant)


def ndcg(ranked: tuple[str, ...], relevant: set[str], k: int) -> float | None:
    if not relevant:
        return None
    seen = set()
    gain = 0.0
    for rank, identity in enumerate(ranked[:k], 1):
        if identity in relevant and identity not in seen:
            gain += 1 / math.log2(rank + 1)
        seen.add(identity)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(k, len(relevant)) + 1))
    return gain / ideal
