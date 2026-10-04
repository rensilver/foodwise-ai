"""Resolve application-issued media IDs only after explicit ownership checks."""

import asyncio
import hashlib
import re
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.infrastructure.media.files import LocalMediaFiles
from food_recommender.infrastructure.media.images import decode_image
from food_recommender.infrastructure.persistence.models.provenance import Media


class AuthorizedQueryMedia:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], files: LocalMediaFiles
    ) -> None:
        self.sessions, self.files = sessions, files

    async def read(
        self, media_id: str, session_id: UUID, *, allow_catalog: bool = False
    ) -> bytes:
        # allow_catalog is application configuration, never an LLM/tool argument.
        if (
            not isinstance(session_id, UUID)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", media_id) is None
        ):
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        try:
            async with self.sessions() as session:
                media = await session.get(Media, media_id)
                if media is None or not (
                    media.owner_session_id == session_id
                    or (allow_catalog and media.source_record_id is not None)
                ):
                    raise ApplicationError(ErrorCode.NOT_FOUND)
            data = await self.files.read(media.storage_key)
        except SQLAlchemyError:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
        if hashlib.sha256(data).hexdigest() != media.content_hash:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        try:
            image = await asyncio.to_thread(decode_image, data)
            image.close()
        except ValueError:
            raise ApplicationError(ErrorCode.INVALID_REQUEST) from None
        return data
