"""Verified catalog quotations shared by style analysis and final synthesis."""

from pydantic import BaseModel

from food_recommender.application.recommendations.evidence_rules import (
    instruction_span,
    publishable_catalog_span,
    supported_span,
)
from food_recommender.retrieval.late_fusion import FusedCandidate


class CatalogOption(BaseModel):
    observation: str
    citation_ids: tuple[str, ...]


def source_options(candidate: FusedCandidate) -> tuple[CatalogOption, ...]:
    options = []
    for citation in candidate.evidence.citations:
        if instruction_span(citation.excerpt):
            continue
        lines = citation.excerpt.splitlines()
        observations = [
            line
            for line in lines
            if line.startswith(
                ("cuisine:", "food_style:", "signatures:", "directions:")
            )
        ]
        if not observations:
            observations = [citation.excerpt[:2000]]
        for observation in observations:
            if publishable_catalog_span(observation) and supported_span(
                observation, (citation,), (citation.id,)
            ):
                options.append(
                    CatalogOption(observation=observation, citation_ids=(citation.id,))
                )
    return tuple(options[:12])
