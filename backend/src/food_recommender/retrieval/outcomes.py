"""Serializable typed evidence outcomes; empty searches never conceal failures."""

from dataclasses import dataclass
from typing import Literal

from food_recommender.application.errors import ErrorCode
from food_recommender.retrieval.fusion import RankedTextCandidate


@dataclass(frozen=True)
class TextRetrievalOutcome:
    status: Literal["success", "no_results", "dependency_error", "invalid_request"]
    candidates: tuple[RankedTextCandidate, ...]
    model: str
    revision: str
    elapsed_ms: float
    limitations: tuple[str, ...] = ()
    error_code: ErrorCode | None = None

    def __post_init__(self) -> None:
        if self.elapsed_ms < 0:
            raise ValueError("Invalid elapsed time")
        if (self.status == "success") != bool(self.candidates):
            raise ValueError("Only successful outcomes contain candidates")
        if (self.status in ("dependency_error", "invalid_request")) != (
            self.error_code is not None
        ):
            raise ValueError("Failure outcomes require a code")
