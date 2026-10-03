"""Shared restaurant/recipe/scoped-review retrieval without LLM search results."""

import asyncio
from dataclasses import replace
from time import perf_counter
from typing import Literal

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.retrieval.dietary import assess, eligible
from food_recommender.retrieval.fusion import RankedTextCandidate, fuse
from food_recommender.retrieval.models import TextPlan
from food_recommender.retrieval.outcomes import TextRetrievalOutcome
from food_recommender.retrieval.ports import TextEncoder, TextSearch


class TextRetrieval:
    def __init__(self, search: TextSearch, encoder: TextEncoder) -> None:
        self.search = search
        self.encoder = encoder
        self.encoding_lock = asyncio.Semaphore(1)

    async def retrieve(self, plan: TextPlan) -> tuple[RankedTextCandidate, ...]:
        async with self.encoding_lock:
            vectors = await asyncio.to_thread(self.encoder.encode, (plan.query,))
        if len(vectors) != 1:
            raise ValueError("Query encoder count mismatch")
        candidates = []
        for category in plan.categories:
            branches = []
            for branch in ("lexical", "dense"):
                branches.append(
                    await self.search.search(
                        plan,
                        category,
                        branch,
                        vectors[0],
                        model=self.encoder.model_id,
                        revision=self.encoder.revision,
                    )
                )
            filtered = []
            for hits in branches:
                filtered.append(
                    tuple(
                        hit
                        for hit in hits
                        if eligible(
                            tuple(
                                assess(c, hit.ingredients, hit.allergens)
                                for c in plan.constraints
                            )
                        )
                    )
                )
            ranked = fuse(filtered[0], filtered[1], plan.limit)
            for item in ranked:
                candidates.append(
                    replace(
                        item,
                        assessments=tuple(
                            assess(c, item.ingredients, item.allergens)
                            for c in plan.constraints
                        ),
                    )
                )
        return tuple(candidates)

    async def run(self, plan: TextPlan, *, timeout: float = 30) -> TextRetrievalOutcome:
        started = perf_counter()
        try:
            async with asyncio.timeout(timeout):
                candidates = await self.retrieve(plan)
            return TextRetrievalOutcome(
                "success" if candidates else "no_results",
                candidates,
                self.encoder.model_id,
                self.encoder.revision,
                (perf_counter() - started) * 1000,
                ("Relevance is not dietary certification",)
                if candidates
                else ("No evidence satisfies the source plan and constraints",),
            )
        except ApplicationError as error:
            status: Literal["invalid_request", "dependency_error"] = (
                "invalid_request"
                if error.code == ErrorCode.INVALID_REQUEST
                else "dependency_error"
            )
            return TextRetrievalOutcome(
                status,
                (),
                self.encoder.model_id,
                self.encoder.revision,
                (perf_counter() - started) * 1000,
                error_code=error.code,
            )
        except (OSError, RuntimeError, TimeoutError):
            return TextRetrievalOutcome(
                "dependency_error",
                (),
                self.encoder.model_id,
                self.encoder.revision,
                (perf_counter() - started) * 1000,
                error_code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            )
        except ValueError:
            return TextRetrievalOutcome(
                "invalid_request",
                (),
                self.encoder.model_id,
                self.encoder.revision,
                (perf_counter() - started) * 1000,
                error_code=ErrorCode.INVALID_REQUEST,
            )
