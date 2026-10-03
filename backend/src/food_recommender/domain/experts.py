"""Typed results for exactly six domain roles and explicit branch outcomes."""

from dataclasses import dataclass, field
from typing import Literal

from food_recommender.domain.evidence import CandidateEvidence, Citation, CitationKind
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import (
    Category,
    EntityRef,
    EvidenceState,
    nonempty,
    unique,
)

FailureCode = Literal[
    "invalid_response",
    "dependency_unavailable",
    "budget_exhausted",
    "cancelled",
    "validation_failed",
    "internal_error",
]
UnavailableCode = Literal[
    "trends_unavailable", "style_unavailable", "nutrition_unavailable"
]


@dataclass(frozen=True)
class AgentSuccess[T]:
    result: T
    status: Literal["success"] = field(default="success", kw_only=True)


@dataclass(frozen=True)
class AgentUnavailable:
    code: UnavailableCode
    status: Literal["unavailable"] = field(default="unavailable", kw_only=True)


@dataclass(frozen=True)
class AgentFailure:
    code: FailureCode
    retryable: bool = False
    status: Literal["failure"] = field(default="failure", kw_only=True)


type ExpertOutcome[T] = AgentSuccess[T] | AgentUnavailable | AgentFailure


@dataclass(frozen=True)
class ProfileResult:
    categories: tuple[Category, ...]
    preferences: Preferences
    clarification: str | None = None

    def __post_init__(self) -> None:
        unique(self.categories)
        if not self.categories:
            raise ValueError("At least one requested category is required")
        if self.clarification is not None:
            nonempty(self.clarification)


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[CandidateEvidence, ...]
    attempts: int
    gaps: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.attempts) is not int or not 1 <= self.attempts <= 3:
            raise ValueError("Retrieval permits the initial query and two refinements")
        unique(tuple(candidate.entity for candidate in self.candidates))
        for category in Category:
            if sum(item.entity.category == category for item in self.candidates) > 20:
                raise ValueError(
                    "Retrieval permits at most twenty candidates per category"
                )


@dataclass(frozen=True)
class TrendClaim:
    claim: str
    entities: tuple[EntityRef, ...]
    citations: tuple[Citation, ...]

    def __post_init__(self) -> None:
        nonempty(self.claim)
        unique(self.entities)
        unique(tuple(citation.id for citation in self.citations))
        if not self.entities or not self.citations:
            raise ValueError(
                "Trend claims require candidate associations and citations"
            )
        if any(
            citation.kind != CitationKind.WEB or citation.published_on is None
            for citation in self.citations
        ):
            raise ValueError(
                "Trend claims require web evidence with a publication date"
            )


@dataclass(frozen=True)
class TrendAnalysis:
    claims: tuple[TrendClaim, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class StyleAssessment:
    entity: EntityRef
    state: EvidenceState
    citation_ids: tuple[str, ...]
    observations: tuple[str, ...]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        unique(self.citation_ids)
        if self.state == EvidenceState.SUPPORTED and not self.citation_ids:
            raise ValueError("Supported style observations require evidence")
        if self.state == EvidenceState.UNKNOWN and self.observations:
            raise ValueError("Unknown style evidence cannot support observations")


@dataclass(frozen=True)
class StyleAnalysis:
    assessments: tuple[StyleAssessment, ...]

    def __post_init__(self) -> None:
        unique(tuple(item.entity for item in self.assessments))


@dataclass(frozen=True)
class NutritionAssessment:
    entity: EntityRef
    state: EvidenceState
    citation_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        unique(self.citation_ids)
        if self.state == EvidenceState.SUPPORTED and not self.citation_ids:
            raise ValueError("Supported compliance requires evidence")


@dataclass(frozen=True)
class NutritionAnalysis:
    assessments: tuple[NutritionAssessment, ...]

    def __post_init__(self) -> None:
        unique(tuple(item.entity for item in self.assessments))
