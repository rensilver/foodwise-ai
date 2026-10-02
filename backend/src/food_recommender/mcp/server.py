"""Independent HTTP MCP scaffold, with no culinary tools yet."""

from pathlib import Path

from fastmcp import FastMCP
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.health import health_payload, local_readiness


class MCPSettings(BaseSettings):
    """MCP receives only the database and read-only media settings."""

    model_config = SettingsConfigDict(
        case_sensitive=True, extra="ignore", frozen=True, hide_input_in_errors=True
    )
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    media_root: Path = Field(validation_alias="MEDIA_ROOT")

    @field_validator("database_url")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        return Settings.validate_database_url(value)

    @field_validator("media_root")
    @classmethod
    def validate_media(cls, value: Path) -> Path:
        return Settings.validate_media_root(value)


def create_app() -> Starlette:
    settings = MCPSettings()
    server = FastMCP("foodwise-ai")

    @server.custom_route("/health/live", methods=["GET"])
    async def live(request: Request) -> JSONResponse:
        return JSONResponse({"status": "alive"})

    @server.custom_route("/health/ready", methods=["GET"])
    async def ready(request: Request) -> JSONResponse:
        payload, status = health_payload(
            await local_readiness(
                settings.database_url.get_secret_value(),
                settings.media_root,
                writable=False,
            )
        )
        return JSONResponse(payload, status_code=status)

    return server.http_app(
        path="/mcp",
        allowed_hosts=["mcp:8001", "localhost:8001", "127.0.0.1:8001"],
        allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    )
