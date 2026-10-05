"""Owned image uploads, private reads and failed-write compensation."""

import hashlib
from collections.abc import Callable
from uuid import UUID, uuid4

from food_recommender.application.media.ports import (
    ImageSanitization,
    MediaReceipt,
    StoredMedia,
    UploadFiles,
)
from food_recommender.application.unit_of_work import UnitOfWork


class MediaService:
    def __init__(
        self,
        transactions: Callable[[], UnitOfWork],
        files: UploadFiles,
        sanitizer: ImageSanitization,
    ) -> None:
        self.transactions, self.files, self.sanitizer = transactions, files, sanitizer

    async def upload(self, owner: UUID, content: bytes, mime_type: str) -> MediaReceipt:
        image = await self.sanitizer.prepare(content, mime_type)
        identity = str(uuid4())
        stored = StoredMedia(
            MediaReceipt(
                identity, image.mime_type, len(image.content), image.width, image.height
            ),
            identity + ".png",
            hashlib.sha256(image.content).hexdigest(),
        )
        await self.files.write(stored.storage_key, image.content)
        try:
            async with self.transactions() as transaction:
                await transaction.media.create(owner, stored)
                await transaction.commit()
        except BaseException:
            await self.files.delete(stored.storage_key)
            raise
        return stored.receipt

    async def read(self, owner: UUID, media_id: str) -> tuple[MediaReceipt, bytes]:
        async with self.transactions() as transaction:
            stored = await transaction.media.get(owner, media_id)
        return stored.receipt, await self.files.read(stored.storage_key)
