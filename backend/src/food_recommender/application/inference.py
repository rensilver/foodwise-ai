"""Provider-neutral inference ports and safe transport diagnostics."""

from typing import Any, Protocol


class Inference(Protocol):
    async def generate(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        *,
        image: str | None = None,
    ) -> str: ...


class InferenceError(Exception):
    def __init__(
        self,
        *,
        retryable: bool = False,
        retry_after: float = 0,
        schema_error: bool = False,
    ) -> None:
        super().__init__("Inference unavailable")
        self.retryable = retryable
        self.retry_after = retry_after
        self.schema_error = schema_error
