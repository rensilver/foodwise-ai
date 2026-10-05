"""Bounded off-loop decoding and metadata-free PNG preparation."""

import asyncio
import io

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.media.ports import SanitizedImage
from food_recommender.infrastructure.media.images import MAX_BYTES, decode_image


class ImageSanitizer:
    def __init__(self) -> None:
        self.slots = asyncio.Semaphore(2)

    async def prepare(self, content: bytes, mime_type: str) -> SanitizedImage:
        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        async with self.slots:
            try:
                return await asyncio.to_thread(self._prepare, content)
            except ValueError:
                raise ApplicationError(ErrorCode.INVALID_REQUEST) from None

    def _prepare(self, content: bytes) -> SanitizedImage:
        image = decode_image(content)
        image.info.clear()
        output = io.BytesIO()
        image.save(output, format="PNG")
        clean = output.getvalue()
        if len(clean) > MAX_BYTES:
            raise ValueError("Prepared image exceeds byte limit")
        return SanitizedImage(clean, "image/png", image.width, image.height)
