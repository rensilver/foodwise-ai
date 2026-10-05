"""Explicit local numeric scores; no datasets, comments, judges or experiment helpers."""

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

DEFINITIONS: dict[str, dict[str, Any]] = {
    "citation_correctness": {
        "range": [0, 1],
        "target": "synthesize-recommendations",
        "denominator": "published citation references",
        "definition": "1 - unsupported citation references / published citation references; inapplicable with no citations",
    },
    "hard_constraint_violations": {
        "range": [0, None],
        "target": "synthesize-recommendations",
        "denominator": "published recommendations under hard restrictions",
        "definition": "count of conflicting or unknown hard-restriction compliance; zero required; inapplicable without hard constraints or recommendations",
    },
    "fabricated_ids": {
        "range": [0, None],
        "target": "synthesize-recommendations",
        "denominator": "published recommendations",
        "definition": "count of recommendations outside retrieved entity set; zero required; inapplicable with no recommendations",
    },
    "expected_outcome": {
        "range": [0, 1],
        "target": "recommend-food",
        "denominator": "one labeled fixture turn",
        "definition": "1 when locally observed clarification/recommendations/abstention equals source-backed label; zero otherwise",
    },
}
EVALUATOR_REVISION = "phase10-audit-v1"


def trace_selected(run: UUID, rate: float) -> bool:
    return int(run.hex, 16) / 2**128 < rate


@dataclass(frozen=True)
class LocalScore:
    metric: str
    value: float
    run: UUID
    observation: str
    fixture_ref: str
    execution: UUID
    denominator: int

    def __post_init__(self) -> None:
        definition = DEFINITIONS.get(self.metric)
        if definition is None or not math.isfinite(self.value) or self.denominator <= 0:
            raise ValueError("Unmeasured or unknown score")
        minimum, maximum = definition["range"]
        if self.value < minimum or maximum is not None and self.value > maximum:
            raise ValueError("Score outside metric range")
        if not re.fullmatch(r"[0-9a-f]{16}", self.observation):
            raise ValueError("Invalid observation association")


def score_payload(
    score: LocalScore, *, sample_rate: float = 1
) -> dict[str, Any] | None:
    if not trace_selected(score.run, sample_rate):
        return None
    fixture = hashlib.sha256(score.fixture_ref.encode()).hexdigest()
    identity = hashlib.sha256(
        f"{score.execution.hex}:{fixture}:{score.metric}:{EVALUATOR_REVISION}".encode()
    ).hexdigest()
    return {
        "name": score.metric,
        "value": score.value,
        "data_type": "NUMERIC",
        "trace_id": score.run.hex,
        "observation_id": score.observation,
        "score_id": identity,
        "metadata": {
            "fixture_ref": fixture,
            "execution": score.execution.hex,
            "evaluator_revision": EVALUATOR_REVISION,
            "denominator": score.denominator,
        },
    }


def export_scores(
    client: Any, scores: list[LocalScore], *, sample_rate: float = 1
) -> int:
    exported = 0
    for score in scores:
        payload = score_payload(score, sample_rate=sample_rate)
        if payload is not None:
            client.create_score(**payload)
            exported += 1
    return exported
