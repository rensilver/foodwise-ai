"""Bounded multipart upload and authorized private image responses."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response

from food_recommender.api.dependencies import (
    browser_session,
    create_browser_session,
    get_services,
)
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.media.ports import MediaReceipt
from food_recommender.application.media.service import MediaService
from food_recommender.application.services import Services

router = APIRouter(prefix="/api/v1/media", tags=["media"])


def media(services: Annotated[Services, Depends(get_services)]) -> MediaService:
    if services.media is None:
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return services.media


@router.post("", status_code=201, response_model=MediaReceipt)
async def upload(
    file: UploadFile,
    owner: Annotated[UUID, Depends(create_browser_session)],
    service: Annotated[MediaService, Depends(media)],
) -> MediaReceipt:
    try:
        content = await file.read(10 * 1024 * 1024 + 1)
        return await service.upload(owner, content, file.content_type or "")
    finally:
        await file.close()


@router.get("/{media_id}", response_class=Response)
async def read(
    media_id: str,
    owner: Annotated[UUID, Depends(browser_session)],
    service: Annotated[MediaService, Depends(media)],
) -> Response:
    receipt, content = await service.read(owner, media_id)
    return Response(
        content,
        media_type=receipt.mime_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
