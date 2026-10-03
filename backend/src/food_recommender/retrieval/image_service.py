"""Bounded off-loop CLIP query encoding and shared category-scoped image search."""

import asyncio

from food_recommender.infrastructure.clip_encoder import validate_clip
from food_recommender.retrieval.models import ImageHit, TextPlan
from food_recommender.retrieval.ports import ImageEncoder, ImageSearch


class ImageRetrieval:
    def __init__(self, search: ImageSearch, encoder: ImageEncoder) -> None:
        self.search, self.encoder = search, encoder
        self.encoding_lock = asyncio.Semaphore(1)

    async def text(self, plan: TextPlan) -> tuple[ImageHit, ...]:
        async with self.encoding_lock:
            vectors = await asyncio.to_thread(self.encoder.encode_texts, (plan.query,))
        if len(vectors) != 1:
            raise ValueError("CLIP query count mismatch")
        return await self.vector(plan, vectors[0])

    async def vector(
        self, plan: TextPlan, vector: tuple[float, ...]
    ) -> tuple[ImageHit, ...]:
        validate_clip(vector, self.encoder.model_id, self.encoder.revision)
        hits: list[ImageHit] = []
        for category in plan.categories:
            hits.extend(
                await self.search.search(
                    plan,
                    category,
                    vector,
                    model=self.encoder.model_id,
                    revision=self.encoder.revision,
                )
            )
        return tuple(hits)
