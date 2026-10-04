"""Validated backend configuration, loaded explicitly without service I/O."""

from __future__ import annotations

import base64
import re
import sys
from argparse import ArgumentParser
from pathlib import Path

from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
_SETUP_GUIDANCE = {
    "GROQ_API_KEY": "Set a fresh Groq API key without whitespace or controls.",
    "GROQ_MODEL": "Set a model identifier without whitespace; default: qwen/qwen3.8-27b.",
    "GROQ_VISION_MODEL": (
        "Set a vision model identifier without whitespace; default: qwen/qwen3.8-27b."
    ),
    "TAVILY_API_KEY": (
        "Set a fresh Tavily API key without whitespace or leave it blank "
        "for unavailable live trends."
    ),
    "DATABASE_URL": (
        "Set a PostgreSQL connection URL with user, host, database and a valid port; "
        "use postgresql:// or postgresql+psycopg://."
    ),
    "MCP_SERVER_URL": "Set an HTTP(S) MCP endpoint without credentials, query or fragment.",
    "MEDIA_ROOT": (
        "Set an absolute media directory other than the filesystem root, without traversal."
    ),
    "ADMIN_PASSWORD_HASH": (
        "Set an Argon2id v19 password hash with m=19456..262144, t=2..10, p=1..16, "
        "a 16..64-byte salt and 32..64-byte digest; quote it in dotenv files."
    ),
}
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
    tavily_api_key: SecretStr | None = Field(
        default=None, validation_alias="TAVILY_API_KEY"
    )
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")
    mcp_server_url: AnyHttpUrl = Field(validation_alias="MCP_SERVER_URL")
    media_root: Path = Field(validation_alias="MEDIA_ROOT")
    minilm_root: Path | None = Field(default=None, validation_alias="MINILM_ROOT")
    allowed_origins: tuple[str, ...] = Field(
        default=(
            "http://localhost",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ),
        validation_alias="ALLOWED_ORIGINS",
    )
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
                raise ValueError(
                    "must be a nonempty token without whitespace or controls"
                )
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
            value.username
            or value.password
            or value.query
            or value.fragment
            or value.port == 0
        ):
            raise ValueError(
                "must be an HTTP(S) endpoint without credentials, query or fragment"
            )
        return value

    @field_validator("media_root")
    @classmethod
    def validate_media_root(cls, value: Path) -> Path:
        if (
            not value.is_absolute()
            or value == Path(value.anchor)
            or ".." in value.parts
            or "\x00" in str(value)
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
                raise ValueError(
                    "Argon2id salt and digest must be valid base64"
                ) from None
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
        raise ConfigurationError(
            "Invalid backend configuration: ENV_FILE (missing file). "
            "Copy .env.example to a local .env and select that file explicitly."
        )
    try:
        return Settings(_env_file=env_file)
    except ValidationError as error:
        issues = error.errors(
            include_input=False, include_context=False, include_url=False
        )
        lines = [
            "Invalid backend configuration. See .env.example and backend/README.md:"
        ]
        for issue in issues:
            field = ".".join(str(part) for part in issue["loc"])
            guidance = _SETUP_GUIDANCE.get(
                field, "Check this setting's documented format."
            )
            lines.append(f"- {field} ({issue['type']}): {guidance}")
        raise ConfigurationError("\n".join(lines)) from None


def main() -> int:
    """Offline syntax check; never prints configuration values or contacts services."""
    parser = ArgumentParser(
        description="Validate backend configuration without service calls."
    )
    parser.add_argument(
        "--env-file", type=Path, help="Explicit local dotenv file to read."
    )
    arguments = parser.parse_args()
    try:
        settings = load_settings(env_file=arguments.env_file)
    except ConfigurationError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(
        "Configuration valid. Service readiness and provider access have not been checked."
    )
    if settings.tavily_api_key is None:
        print("Live trends unavailable: set TAVILY_API_KEY to enable trend search.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
