"""Shared HTTP error schemas and ASGI observation boundary for both services."""

import asyncio
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.infrastructure.observability import Runtime, request_id, run_id

_ERRORS = {
    ErrorCode.UNAUTHORIZED: (401, "Administrator authentication is required.", False),
    ErrorCode.FORBIDDEN: (403, "The request is not permitted.", False),
    ErrorCode.INVALID_REQUEST: (422, "The request is invalid.", False),
    ErrorCode.NOT_FOUND: (404, "The requested resource was not found.", False),
    ErrorCode.CONFLICT: (409, "The request conflicts with the current state.", False),
    ErrorCode.DEPENDENCY_UNAVAILABLE: (503, "A required service is unavailable.", True),
    ErrorCode.INTERNAL_ERROR: (500, "The request could not be completed.", False),
}


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    code: ErrorCode
    message: str
    retryable: bool


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    error: ErrorDetail
    request_id: UUID | None


def error_response(code: ErrorCode, *, status: int | None = None) -> JSONResponse:
    default_status, message, retryable = _ERRORS[code]
    payload = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, retryable=retryable),
        request_id=request_id.get(),
    )
    return JSONResponse(
        payload.model_dump(mode="json"), status_code=status or default_status
    )


class ObservedHTTP:
    """Pure ASGI middleware preserves context across async dependencies/streams.

    It never consumes request bodies or logs URLs/headers. Once headers have
    started, failures propagate; future SSE handlers must emit typed events.
    Cancellation propagates without being turned into an ordinary failure.
    """

    def __init__(self, app: ASGIApp, *, runtime: Runtime) -> None:
        self.app = app
        self.runtime = runtime

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        identifier = self.runtime.new_id()
        token = request_id.set(identifier)
        run_token = run_id.set(None)
        started = self.runtime.clock()
        status = 500
        headers_started = False
        code: ErrorCode | None = None
        cancelled = False

        async def observed_send(message: Message) -> None:
            nonlocal status, headers_started
            if message["type"] == "http.response.start":
                status = message["status"]
                headers_started = True
                message = dict(message)
                message["headers"] = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", str(identifier).encode("ascii"))]
            await send(message)

        try:
            try:
                await self.app(scope, receive, observed_send)
            except Exception as error:
                code = (
                    error.code
                    if isinstance(error, ApplicationError)
                    else ErrorCode.INTERNAL_ERROR
                )
                if headers_started:
                    raise
                await error_response(code)(scope, receive, observed_send)
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            try:
                self.runtime.logger.log(
                    40 if status >= 500 else 20,
                    "",
                    extra={
                        "event": "request_cancelled"
                        if cancelled
                        else (
                            "request_failed"
                            if code or status >= 400
                            else "request_completed"
                        ),
                        "status": status if headers_started else None,
                        "duration_ms": max(0, (self.runtime.clock() - started) * 1000),
                        "error_code": code,
                    },
                )
            finally:
                run_id.reset(run_token)
                request_id.reset(token)
