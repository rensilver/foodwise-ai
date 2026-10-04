"""Allowlisted JSON logs. Never interpolate untrusted messages or exception text."""

import json
import logging
import math
import sys
import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TextIO
from uuid import UUID, uuid4

from food_recommender.application.errors import ErrorCode

request_id: ContextVar[UUID | None] = ContextVar("request_id", default=None)
run_id: ContextVar[UUID | None] = ContextVar("run_id", default=None)
_EVENTS = {
    "request_completed",
    "request_failed",
    "request_cancelled",
    "diagnostic",
    "agent_completed",
    "run_completed",
    "run_exhausted",
}
_COUNTERS = {
    "status",
    "duration_ms",
    "retrieval_attempts",
    "token_usage",
    "search_calls",
    "openai_calls",
    "tool_calls",
}


class StructuredFormatter(logging.Formatter):
    """Unknown fields and free-form SDK/server messages are deliberately omitted."""

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", None)
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": logging.getLevelName(record.levelno)
            if record.levelno in {10, 20, 30, 40, 50}
            else "INFO",
            "event": event
            if isinstance(event, str) and event in _EVENTS
            else "diagnostic",
        }
        for name, context in (("request_id", request_id), ("run_id", run_id)):
            value = getattr(record, name, context.get())
            if isinstance(value, UUID):
                payload[name] = str(value)
        stage = getattr(record, "stage", None)
        if stage in {
            "profile",
            "retrieval",
            "trend",
            "style",
            "nutrition",
            "recommendation",
        }:
            payload["stage"] = stage
        code = getattr(record, "error_code", None)
        if isinstance(code, ErrorCode):
            payload["error_code"] = code.value
        for name in _COUNTERS:
            value = getattr(record, name, None)
            if (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value >= 0
            ):
                payload[name] = value
        return json.dumps(payload, allow_nan=False)


def configure_logging(*, stream: TextIO | None = None) -> logging.Logger:
    """Install process-wide redaction, including Uvicorn/SDK loggers, on stderr.

    Call only at a service composition root. Repeated calls replace handlers;
    embeddings/tests can inject their own Runtime instead of changing logging.
    """
    handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.handlers = []
            logger.propagate = True
    return logging.getLogger("foodwise")


@dataclass(frozen=True)
class Runtime:
    logger: logging.Logger
    clock: Callable[[], float] = time.monotonic
    new_id: Callable[[], UUID] = field(default=uuid4)
