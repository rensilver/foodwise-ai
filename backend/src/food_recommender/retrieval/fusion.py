"""Equal-weight RRF at entity ranks; duplicate chunks supply evidence only."""

from dataclasses import dataclass

from food_recommender.domain.evidence import CandidateEvidence
from food_recommender.domain.values import EntityRef
from food_recommender.retrieval.dietary import DietaryAssessment
from food_recommender.retrieval.models import TextHit


@dataclass(frozen=True)
class RankedTextCandidate:
    evidence: CandidateEvidence
    name: str
    ingredients: tuple[str, ...] | None
    allergens: tuple[str, ...] | None
    lexical_score: float | None
    cosine_similarity: float | None
    rrf_score: float
    assessments: tuple[DietaryAssessment, ...] = ()


def entity_ranks(hits: tuple[TextHit, ...]) -> dict[EntityRef, int]:
    ranks: dict[EntityRef, int] = {}
    for hit in hits:
        if hit.entity not in ranks:
            ranks[hit.entity] = len(ranks) + 1
    return ranks


def fuse(
    lexical: tuple[TextHit, ...], dense: tuple[TextHit, ...], limit: int
) -> tuple[RankedTextCandidate, ...]:
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Result limit must be 1..20")
    hits: dict[EntityRef, list[TextHit]] = {}
    for hit in (*lexical, *dense):
        hits.setdefault(hit.entity, []).append(hit)
    if not hits:
        return ()
    if len({ref.category for ref in hits}) != 1:
        raise ValueError("Fuse each category separately")
    lr, dr = entity_ranks(lexical), entity_ranks(dense)
    scores = {
        ref: (0.5 / (60 + lr[ref]) if ref in lr else 0)
        + (0.5 / (60 + dr[ref]) if ref in dr else 0)
        for ref in hits
    }
    low, high = min(scores.values()), max(scores.values())
    result = []
    for ref in sorted(hits, key=lambda ref: (-scores[ref], ref.id))[:limit]:
        evidence = hits[ref]
        first = evidence[0]
        normalized = 1.0 if low == high else (scores[ref] - low) / (high - low)
        citations = {hit.citation.id: hit.citation for hit in evidence}
        lexical_scores = [
            h.lexical_score for h in evidence if h.lexical_score is not None
        ]
        cosine_scores = [
            h.cosine_similarity for h in evidence if h.cosine_similarity is not None
        ]
        result.append(
            RankedTextCandidate(
                CandidateEvidence(
                    entity=ref,
                    citations=tuple(citations[key] for key in sorted(citations)),
                    relevance=normalized,
                    text_score=normalized,
                    lexical_rank=lr.get(ref),
                    dense_rank=dr.get(ref),
                ),
                first.name,
                first.ingredients,
                first.allergens,
                max(lexical_scores) if lexical_scores else None,
                max(cosine_scores) if cosine_scores else None,
                scores[ref],
            )
        )
    return tuple(result)
