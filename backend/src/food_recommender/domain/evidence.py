"""Source-backed evidence. Relevance scores do not certify dietary compliance."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from food_recommender.domain.values import EntityRef, nonempty, unique, unit_score


class CitationKind(StrEnum):
    CATALOG = "catalog"
    WEB = "web"


@dataclass(frozen=True)
class Citation:
    id: str
    kind: CitationKind
    source_id: str
    excerpt: str
    entity: EntityRef | None = None
    record_id: str | None = None
    document_id: str | None = None
    url: str | None = None
    published_on: date | None = None
    retrieved_at: datetime | None = None
    attribution: Literal["imported", "generated", "source"] = "imported"

    def __post_init__(self) -> None:
        for value in (self.id, self.source_id, self.excerpt):
            nonempty(value)
        if self.kind == CitationKind.CATALOG:
            if (
                self.entity is None
                or self.record_id is None
                or self.document_id is None
            ):
                raise ValueError(
                    "Catalog citations require entity, record and document IDs"
                )
        elif self.url is None or self.retrieved_at is None:
            raise ValueError("Web citations require a URL and retrieval timestamp")
        for optional_id in (self.record_id, self.document_id):
            if optional_id is not None:
                nonempty(optional_id)
        if self.url is not None:
            parsed = urlsplit(self.url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Citation URL must be HTTP(S) without credentials")
        if self.retrieved_at is not None and self.retrieved_at.utcoffset() is None:
            raise ValueError("Retrieval timestamp must have a timezone")


@dataclass(frozen=True)
class CandidateEvidence:
    entity: EntityRef
    citations: tuple[Citation, ...]
    relevance: float
    text_score: float | None = None
    image_score: float | None = None
    lexical_rank: int | None = None
    dense_rank: int | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        unit_score(self.relevance)
        for score in (self.text_score, self.image_score):
            if score is not None:
                unit_score(score)
        for rank in (self.lexical_rank, self.dense_rank):
            if rank is not None and (type(rank) is not int or rank < 1):
                raise ValueError("Retrieval ranks must be positive integers")
        if not self.citations:
            raise ValueError("Candidates require source evidence")
        unique(tuple(citation.id for citation in self.citations))
        if any(
            citation.kind != CitationKind.CATALOG or citation.entity != self.entity
            for citation in self.citations
        ):
            raise ValueError(
                "Candidate citations must refer to the same catalog entity"
            )
