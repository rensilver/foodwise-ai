"""Explicit regional configuration. Credentials alone never enable telemetry."""

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelemetrySettings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=True, extra="ignore", hide_input_in_errors=True
    )
    enabled: bool = Field(False, validation_alias="LANGFUSE_ENABLED")
    base_url: str | None = Field(None, validation_alias="LANGFUSE_BASE_URL")
    public_key: SecretStr | None = Field(None, validation_alias="LANGFUSE_PUBLIC_KEY")
    secret_key: SecretStr | None = Field(None, validation_alias="LANGFUSE_SECRET_KEY")
    correlation_key: SecretStr | None = Field(
        None, validation_alias="LANGFUSE_CORRELATION_KEY"
    )
    conversation_export_verified: bool = Field(
        False, validation_alias="LANGFUSE_CONVERSATION_EXPORT_VERIFIED"
    )
    environment: str = Field(
        "local",
        pattern=r"^[a-z][a-z0-9_-]{0,39}$",
        validation_alias="LANGFUSE_TRACING_ENVIRONMENT",
    )
    revision: str = Field(
        "development",
        pattern=r"^[A-Za-z0-9._-]{1,64}$",
        validation_alias="LANGFUSE_RELEASE",
    )
    sample_rate: float = Field(1, ge=0, le=1, validation_alias="LANGFUSE_SAMPLE_RATE")

    @model_validator(mode="after")
    def explicit_region_and_keys(self) -> "TelemetrySettings":
        if self.enabled and (
            self.base_url
            not in {
                "https://us.cloud.langfuse.com",
                "https://cloud.langfuse.com",
                "https://jp.cloud.langfuse.com",
            }
            or not self.public_key
            or not self.secret_key
            or not self.correlation_key
        ):
            raise ValueError(
                "Enabled telemetry requires explicit approved Cloud region and dedicated keys"
            )
        return self
