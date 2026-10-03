"""Explainable entity-level late fusion; each category has its own score scale."""

import math
from dataclasses import dataclass

from food_recommender.domain.evidence import CandidateEvidence
from food_recommender.domain.values import EntityRef
from food_recommender.retrieval.dietary import DietaryAssessment
from food_recommender.retrieval.fusion import RankedTextCandidate
from food_recommender.retrieval.models import ImageHit


@dataclass(frozen=True)
class FusionWeights:
    text: float = 0.6
    image: float = 0.4

    def __post_init__(self) -> None:
        if (
            any(not math.isfinite(w) or w < 0 for w in (self.text, self.image))
            or not math.isfinite(self.text + self.image)
            or self.text + self.image == 0
        ):
            raise ValueError("Fusion weights must be finite, nonnegative and nonzero")


@dataclass(frozen=True)
class FusedCandidate:
    evidence: CandidateEvidence
    name: str
    ingredients: tuple[str, ...] | None
    allergens: tuple[str, ...] | None
    rrf_score: float | None
    lexical_score: float | None
    text_cosine_similarity: float | None
    image_cosine_similarity: float | None
    media_ids: tuple[str, ...]
    assessments: tuple[DietaryAssessment, ...] = ()


@dataclass(frozen=True)
class FusionResult:
    candidates: tuple[FusedCandidate, ...]
    text_weight: float
    image_weight: float
    limitations: tuple[str, ...] = ()


def normalize(scores: dict[EntityRef, float]) -> dict[EntityRef, float]:
    if any(not math.isfinite(v) for v in scores.values()):
        raise ValueError("Nonfinite fusion component")
    if not scores:
        return {}
    low, high = min(scores.values()), max(scores.values())
    return {
        ref: 1.0 if low == high else (v - low) / (high - low)
        for ref, v in scores.items()
    }


def late_fuse(
    text: tuple[RankedTextCandidate, ...],
    images: tuple[ImageHit, ...],
    limit: int,
    *,
    weights: FusionWeights = FusionWeights(),
) -> FusionResult:
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Fusion result limit must be 1..20")
    refs = {c.evidence.entity for c in text} | {h.entity for h in images}
    if len({ref.category for ref in refs}) > 1:
        raise ValueError("Fuse categories separately")
    if any(
        not math.isfinite(h.cosine_similarity)
        or not -1.001 <= h.cosine_similarity <= 1.001
        for h in images
    ):
        raise ValueError("Invalid image similarity")
    text_by_ref: dict[EntityRef, RankedTextCandidate] = {}
    for candidate in text:
        ref = candidate.evidence.entity
        if ref not in text_by_ref or candidate.rrf_score > text_by_ref[ref].rrf_score:
            text_by_ref[ref] = candidate
    image_by_ref: dict[EntityRef, list[ImageHit]] = {}
    media_owners: dict[str, EntityRef] = {}
    for image in images:
        if (
            image.media_id in media_owners
            and media_owners[image.media_id] != image.entity
        ):
            raise ValueError("Duplicate media belongs to different entities")
        media_owners[image.media_id] = image.entity
        if image.citation.entity != image.entity:
            raise ValueError("Image citation entity mismatch")
        image_by_ref.setdefault(image.entity, []).append(image)
    text_scores = normalize({ref: c.rrf_score for ref, c in text_by_ref.items()})
    image_scores = normalize(
        {
            ref: max(h.cosine_similarity for h in hits)
            for ref, hits in image_by_ref.items()
        }
    )
    limitations = tuple(
        f"{name} modality has no eligible evidence; active weights renormalized"
        for name, configured, values in (
            ("Text", weights.text, text_scores),
            ("Image", weights.image, image_scores),
        )
        if configured > 0 and not values
    )
    active_text = weights.text if text_scores else 0.0
    active_image = weights.image if image_scores else 0.0
    total = active_text + active_image
    if total == 0:
        return FusionResult(
            (), 0.0, 0.0, limitations + ("No active modality has eligible evidence",)
        )
    tw, iw = active_text / total, active_image / total
    refs = (set(text_scores) if tw else set()) | (set(image_scores) if iw else set())
    scores = {
        ref: tw * text_scores.get(ref, 0) + iw * image_scores.get(ref, 0)
        for ref in refs
    }
    result = []
    for ref in sorted(refs, key=lambda ref: (-scores[ref], ref.id))[:limit]:
        tc = text_by_ref.get(ref)
        ih = image_by_ref.get(ref, [])
        first = ih[0] if ih else None
        citations = {
            citation.id: citation
            for candidate in text
            if candidate.evidence.entity == ref
            for citation in candidate.evidence.citations
        }
        citations.update({h.citation.id: h.citation for h in ih})
        evidence = CandidateEvidence(
            entity=ref,
            citations=tuple(citations[key] for key in sorted(citations)),
            relevance=scores[ref],
            text_score=text_scores.get(ref, 0.0) if text_scores else None,
            image_score=image_scores.get(ref, 0.0) if image_scores else None,
            lexical_rank=tc.evidence.lexical_rank if tc else None,
            dense_rank=tc.evidence.dense_rank if tc else None,
            limitations=limitations,
        )
        base = tc if tc is not None else first
        if base is None:
            raise ValueError("Candidate lacks evidence")
        result.append(
            FusedCandidate(
                evidence,
                base.name,
                base.ingredients,
                base.allergens,
                tc.rrf_score if tc else None,
                tc.lexical_score if tc else None,
                tc.cosine_similarity if tc else None,
                max(h.cosine_similarity for h in ih) if ih else None,
                tuple(sorted({h.media_id for h in ih})),
                tc.assessments if tc else (),
            )
        )
    return FusionResult(tuple(result), tw, iw, limitations)
