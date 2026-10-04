"""HTTP response contracts, sharing the application's domain types."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Path
from pydantic import BaseModel, ConfigDict, Field, RootModel, SecretStr

from food_recommender.application.admin_catalog import RecipePatch, RestaurantPatch
from food_recommender.application.ports import MessageSnapshot
from food_recommender.domain.events import ProgressEvents
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.values import Category
from food_recommender.ingestion.extraction import RecipeFields, RestaurantFields


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


class LiveResponse(ResponseModel):
    status: Literal["alive"] = "alive"


class HealthResponse(ResponseModel):
    status: Literal["ready", "unavailable"]
    dependencies: dict[str, Literal["ready", "unavailable"]]


class StreamContract(
    RootModel[Annotated[ProgressEvents, Field(discriminator="event")]]
):
    """One SSE data payload, with the event discriminator used by the runtime."""


Identity = Annotated[
    str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.:-]+$")
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class PreviewRequest(Input):
    category: Category
    text: str = Field(min_length=1, max_length=65536, pattern=r"\S")


class RestaurantCreate(Input):
    fields: RestaurantFields


class RecipeCreate(Input):
    fields: RecipeFields


class RestaurantUpdate(Input):
    expected_version: int = Field(ge=1)
    fields: RestaurantPatch


class RecipeUpdate(Input):
    expected_version: int = Field(ge=1)
    fields: RecipePatch


class DeleteRequest(Input):
    expected_version: int = Field(ge=1)
    confirm_id: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    password: SecretStr = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    csrf_token: str
    expires_at: datetime
