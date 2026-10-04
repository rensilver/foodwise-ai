"""HTTP response contracts, sharing the application's domain types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from food_recommender.application.ports import MessageSnapshot
from food_recommender.domain.preferences import Preferences


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ConversationResponse(ResponseModel):
    id: UUID
    created_at: datetime


class HistoryResponse(ConversationResponse):
    messages: tuple[MessageSnapshot, ...]
    preferences: Preferences | None


class DeletionResponse(ResponseModel):
    conversation_id: UUID
    cleanup_pending: bool
