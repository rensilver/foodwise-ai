"""Source-backed role fixtures; provider calls remain offline."""

import json

from food_recommender.domain.evidence import CandidateEvidence, Citation, CitationKind
from food_recommender.domain.values import Category, EntityRef
from food_recommender.retrieval.late_fusion import FusedCandidate


def candidate(
    identity="recipe:1", *, category=Category.RECIPE, ingredients=("rice", "tomato")
):
    entity = EntityRef(category, identity)
    citation = Citation(
        f"citation:{identity}",
        CitationKind.CATALOG,
        "synthetic-source",
        "Italian tomato rice simmered with basil",
        entity,
        identity,
        f"doc:{identity}",
    )
    evidence = CandidateEvidence(entity, (citation,), 1)
    return FusedCandidate(
        evidence, "Italian tomato rice", ingredients, None, 0.02, 1, 0.8, None, ()
    )


class Reply:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def generate(self, messages, schema, *, image=None):
        self.calls.append(json.loads(messages[-1]["content"]))
        return (
            self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        )
