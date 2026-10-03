"""Shared multimodal retrieval with separate categories and conservative constraints."""

import asyncio
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Literal
from uuid import UUID

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.domain.values import Category
from food_recommender.retrieval.dietary import assess, eligible
from food_recommender.retrieval.fusion import RankedTextCandidate
from food_recommender.retrieval.image_service import ImageRetrieval
from food_recommender.retrieval.late_fusion import (
    FusedCandidate,
    FusionResult,
    FusionWeights,
    late_fuse,
)
from food_recommender.retrieval.models import ImageHit, TextPlan
from food_recommender.retrieval.service import TextRetrieval


@dataclass(frozen=True)
class CategoryFusion:
    category: Category
    fusion: FusionResult


@dataclass(frozen=True)
class MultimodalOutcome:
    status: Literal["success", "no_results", "dependency_error", "invalid_request"]
    candidates: tuple[FusedCandidate, ...]
    categories: tuple[CategoryFusion, ...]
    elapsed_ms: float
    limitations: tuple[str, ...] = ()
    error_code: ErrorCode | None = None

    def __post_init__(self) -> None:
        if self.elapsed_ms < 0 or (self.status == "success") != bool(self.candidates):
            raise ValueError("Invalid multimodal outcome")
        if (self.status in ("dependency_error", "invalid_request")) != (
            self.error_code is not None
        ):
            raise ValueError("Failure outcomes require a code")


class MultimodalRetrieval:
    def __init__(
        self, text: TextRetrieval | None, images: ImageRetrieval | None
    ) -> None:
        self.text, self.images = text, images

    async def run(
        self,
        plan: TextPlan,
        *,
        media_id: str | None = None,
        session_id: UUID | None = None,
        use_text: bool = True,
        use_images: bool = True,
        weights: FusionWeights = FusionWeights(),
        timeout: float = 30,
    ) -> MultimodalOutcome:
        started = perf_counter()
        try:
            if (not use_text and not use_images) or (
                media_id is not None and (session_id is None or not use_images)
            ):
                raise ValueError("Invalid modality selection/ownership context")
            async with asyncio.timeout(timeout):
                return await self._run(
                    plan, media_id, session_id, use_text, use_images, weights, started
                )
        except ApplicationError as error:
            invalid = error.code in (ErrorCode.INVALID_REQUEST, ErrorCode.NOT_FOUND)
            return MultimodalOutcome(
                "invalid_request" if invalid else "dependency_error",
                (),
                (),
                (perf_counter() - started) * 1000,
                error_code=error.code,
            )
        except ValueError:
            return MultimodalOutcome(
                "invalid_request",
                (),
                (),
                (perf_counter() - started) * 1000,
                error_code=ErrorCode.INVALID_REQUEST,
            )
        except (OSError, RuntimeError, TimeoutError):
            return MultimodalOutcome(
                "dependency_error",
                (),
                (),
                (perf_counter() - started) * 1000,
                error_code=ErrorCode.DEPENDENCY_UNAVAILABLE,
            )

    async def _run(
        self,
        plan: TextPlan,
        media_id: str | None,
        session_id: UUID | None,
        use_text: bool,
        use_images: bool,
        weights: FusionWeights,
        started: float,
    ) -> MultimodalOutcome:
        text: tuple[RankedTextCandidate, ...] = ()
        images: tuple[ImageHit, ...] = ()
        limitations = []
        failed = False
        if media_id is not None and self.images is None:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        if media_id is not None and weights.image == 0:
            raise ValueError("Image query requires an active image modality")
        if use_images and weights.image > 0:
            if self.images is None:
                failed = True
                limitations.append("Image dependency unavailable")
            else:
                try:
                    # Ownership errors abort the request; text cannot mask them.
                    images = (
                        await self.images.image(plan, media_id, session_id)
                        if media_id is not None and session_id is not None
                        else await self.images.text(plan)
                    )
                except ApplicationError as error:
                    if error.code in (ErrorCode.NOT_FOUND, ErrorCode.INVALID_REQUEST):
                        raise
                    failed = True
                    limitations.append("Image dependency unavailable")
                except (OSError, RuntimeError):
                    failed = True
                    limitations.append("Image dependency unavailable")
        if use_text and weights.text > 0:
            if self.text is None:
                failed = True
                limitations.append("Text dependency unavailable")
            else:
                outcome = await self.text.run(plan)
                if outcome.status == "invalid_request":
                    raise ApplicationError(ErrorCode.INVALID_REQUEST)
                if outcome.status == "dependency_error":
                    failed = True
                    limitations.append("Text dependency unavailable")
                text = outcome.candidates
        effective = FusionWeights(
            weights.text if use_text else 0, weights.image if use_images else 0
        )
        categories = []
        for category in plan.categories:
            # Revalidate all modalities at the shared boundary before fusion.
            category_text = tuple(
                c
                for c in text
                if c.evidence.entity.category == category
                and eligible(
                    tuple(
                        assess(r, c.ingredients, c.allergens) for r in plan.constraints
                    )
                )
            )
            category_images = tuple(
                h
                for h in images
                if h.entity.category == category
                and eligible(
                    tuple(
                        assess(r, h.ingredients, h.allergens) for r in plan.constraints
                    )
                )
            )
            result = late_fuse(
                category_text, category_images, plan.limit, weights=effective
            )
            candidates = tuple(
                replace(
                    c,
                    assessments=tuple(
                        assess(r, c.ingredients, c.allergens) for r in plan.constraints
                    ),
                )
                for c in result.candidates
            )
            categories.append(
                CategoryFusion(category, replace(result, candidates=candidates))
            )
        candidates = tuple(
            c
            for category_result in categories
            for c in category_result.fusion.candidates
        )
        status: Literal["success", "no_results", "dependency_error"] = (
            "success" if candidates else "dependency_error" if failed else "no_results"
        )
        limitations.extend(
            f"{c.category.value}: {gap}"
            for c in categories
            for gap in c.fusion.limitations
        )
        return MultimodalOutcome(
            status,
            candidates,
            tuple(categories),
            (perf_counter() - started) * 1000,
            tuple(limitations),
            ErrorCode.DEPENDENCY_UNAVAILABLE if status == "dependency_error" else None,
        )
