"""Validated backend configuration, loaded explicitly without service I/O."""

from __future__ import annotations

import base64
import re
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
_ARGON2ID = re.compile(
    r"\$argon2id\$v=19\$m=([0-9]{1,6}),t=([0-9]{1,2}),p=([0-9]{1,2})"
    r"\$([A-Za-z0-9+/]{22,86})\$([A-Za-z0-9+/]{43,86})"
)


class ConfigurationError(ValueError):
    """Configuration failure whose message contains no supplied values."""


class Settings(BaseSettings):
    """Process settings; instantiate at startup and inject into adapters.

    Environment names are explicit and case-sensitive. No dotenv file is read
    unless selected by the caller. Secret values require explicit unwrapping
    inside their owning adapter; this model is never an API response.
    """

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",  # A selected dotenv file may also configure other services.
        frozen=True,
        hide_input_in_errors=True,
    )

    groq_api_key: SecretStr = Field(validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default=DEFAULT_GROQ_MODEL, validation_alias="GROQ_MODEL")
    groq_vision_model: str = Field(
        default=DEFAULT_GROQ_MODEL, validation_alias="GROQ_VISION_MODEL"
    )
    tavily_api_key: SecretStr | None = Field(default=None, validation_alias="TAVILY_API_KEY")
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    mcp_server_url: AnyHttpUrl = Field(validation_alias="MCP_SERVER_URL")
    media_root: Path = Field(validation_alias="MEDIA_ROOT")
    admin_password_hash: SecretStr = Field(validation_alias="ADMIN_PASSWORD_HASH")

    @field_validator("tavily_api_key", mode="before")
    @classmethod
    def allow_unconfigured_trends(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("groq_api_key", "tavily_api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            raw = value.get_secret_value()
            if not raw or any(
                character.isspace() or ord(character) < 32 for character in raw
            ):
                raise ValueError("must be a nonempty token without whitespace or controls")
        return value

    @field_validator("groq_model", "groq_vision_model")
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        # Check syntax only. Provider access/capabilities need an opt-in smoke check.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", value):
            raise ValueError("must be a nonempty model identifier without whitespace")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        try:
            url = make_url(raw)
        except (ArgumentError, ValueError):
            raise ValueError("must be a valid PostgreSQL URL") from None
        if (
            url.drivername not in {"postgresql", "postgresql+psycopg"}
            or not url.host
            or not url.username
            or not url.database
            or any(character.isspace() or ord(character) < 32 for character in raw)
            or (url.port is not None and not 1 <= url.port <= 65535)
        ):
            raise ValueError(
                "must use PostgreSQL/psycopg with host, user, database and a valid port"
            )
        # Explicit psycopg selects the locked driver for both sync and async engines.
        return SecretStr(
            url.set(drivername="postgresql+psycopg").render_as_string(
                hide_password=False
            )
        )

    @field_validator("mcp_server_url")
    @classmethod
    def validate_mcp_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if (
            value.username or value.password or value.query
            or value.fragment or value.port == 0
        ):
            raise ValueError(
                "must be an HTTP(S) endpoint without credentials, query or fragment"
            )
        return value

    @field_validator("media_root")
    @classmethod
    def validate_media_root(cls, value: Path) -> Path:
        if (
            not value.is_absolute() or value == Path(value.anchor)
            or ".." in value.parts or "\x00" in str(value)
        ):
            raise ValueError(
                "must be an absolute non-root path without traversal or NUL bytes"
            )
        # The mounted directory may not exist yet. Readiness/creation belongs to startup.
        return value

    @field_validator("admin_password_hash")
    @classmethod
    def validate_admin_hash(cls, value: SecretStr) -> SecretStr:
        match = _ARGON2ID.fullmatch(value.get_secret_value())
        if match is None:
            raise ValueError("must be an Argon2id v19 PHC password hash")
        memory, iterations, parallelism = (int(part) for part in match.group(1, 2, 3))
        if not (
            19456 <= memory <= 262144
            and 2 <= iterations <= 10
            and 1 <= parallelism <= 16
        ):
            raise ValueError(
                "Argon2id costs must be m=19456..262144 KiB, t=2..10, p=1..16"
            )
        for encoded, minimum in ((match.group(4), 16), (match.group(5), 32)):
            try:
                decoded = base64.b64decode(
                    encoded + "=" * (-len(encoded) % 4), validate=True
                )
            except ValueError:
                raise ValueError("Argon2id salt and digest must be valid base64") from None
            if (
                not minimum <= len(decoded) <= 64
                or base64.b64encode(decoded).decode().rstrip("=") != encoded
            ):
                raise ValueError(
                    "Argon2id salt/digest must use canonical base64 and sufficient length"
                )
        # This validates the encoding and costs, not the administrator's password.
        return value


def load_settings(*, env_file: Path | None = None) -> Settings:
    """Load fresh settings from the environment and an optional dotenv file.

    Use this entry point at startup to keep validation failures free of input
    values. Direct Settings users must omit input/context when inspecting
    ValidationError.errors(); hide_input_in_errors only protects its text form.
    """
    if env_file is not None and not env_file.is_file():
        raise ConfigurationError("Invalid backend configuration: ENV_FILE (missing file)")
    try:
        return Settings(_env_file=env_file)
    except ValidationError as error:
        issues = error.errors(include_input=False, include_context=False, include_url=False)
        summary = "; ".join(
            f"{'.'.join(str(part) for part in issue['loc'])} ({issue['type']})"
            for issue in issues
        )
        raise ConfigurationError(f"Invalid backend configuration: {summary}") from None
