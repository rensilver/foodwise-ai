"""Independent MCP process configuration, without provider/admin settings."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from food_recommender.infrastructure.config import Settings


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True, extra="ignore", frozen=True, hide_input_in_errors=True
    )
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    media_root: Path = Field(validation_alias="MEDIA_ROOT")

    minilm_root: Path | None = Field(default=None, validation_alias="MINILM_ROOT")
    clip_root: Path | None = Field(default=None, validation_alias="CLIP_ROOT")

    @field_validator("minilm_root", "clip_root")
    @classmethod
    def validate_model_root(cls, value: Path | None) -> Path | None:
        return Settings.validate_media_root(value) if value is not None else None

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        return Settings.validate_database_url(value)

    @field_validator("media_root")
    @classmethod
    def validate_media(cls, value: Path) -> Path:
        return Settings.validate_media_root(value)
