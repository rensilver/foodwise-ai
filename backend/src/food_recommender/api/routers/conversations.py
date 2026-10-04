"""Conversation HTTP behavior over the owned conversation use case."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from food_recommender.api.dependencies import (
    browser_session,
    conversations,
    create_browser_session,
)
from food_recommender.api.schemas import (
    ConversationResponse,
    DeletionResponse,
    HistoryResponse,
)
from food_recommender.application.conversations import ConversationService

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])
Service = Annotated[ConversationService, Depends(conversations)]
Owner = Annotated[UUID, Depends(browser_session)]


@router.post("", status_code=201, response_model=ConversationResponse)
async def create(
    service: Service, owner: Annotated[UUID, Depends(create_browser_session)]
) -> ConversationResponse:
    return ConversationResponse.model_validate(await service.create(owner))


@router.get("/{conversation_id}", response_model=HistoryResponse)
async def history(
    conversation_id: UUID, owner: Owner, service: Service
) -> HistoryResponse:
    conversation, messages, profile = await service.history(owner, conversation_id)
    return HistoryResponse(
        id=conversation.id,
        created_at=conversation.created_at,
        messages=messages,
        preferences=profile,
    )


@router.delete("/{conversation_id}", response_model=DeletionResponse)
async def delete(
    conversation_id: UUID, owner: Owner, service: Service
) -> DeletionResponse:
    return DeletionResponse.model_validate(await service.delete(owner, conversation_id))
