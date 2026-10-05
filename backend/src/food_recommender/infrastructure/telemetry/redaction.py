"""Rebuild OTLP exports from an allowlist, discarding events/resources/errors."""

import math
import re
from typing import Any

NAMES = {
    "recommend-food",
    "build-profile",
    "retrieve-candidates",
    "analyze-trends",
    "analyze-style",
    "assess-nutrition",
    "synthesize-recommendations",
    "request-structured-response",
    "get_restaurant_info",
    "recommend_by_vibe",
    "get_review",
    "search_restaurants",
    "search_recipes",
    "search_images",
    "search_food_trends",
}
KINDS = {"chain", "agent", "generation", "retriever", "tool"}
COUNTERS = {
    "duration_ms",
    "attempt",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "search_calls",
}
OUTCOMES = {
    "success",
    "failure",
    "unavailable",
    "cancelled",
    "exhausted",
    "clarification",
}


def safe_attributes(attributes: Any) -> dict[str, Any]:
    result = {}
    for key, value in (attributes or {}).items():
        if key == "langfuse.observation.type" and value in KINDS:
            result[key] = value
        elif (
            key in {"langfuse.environment", "langfuse.release"}
            and isinstance(value, str)
            and re.fullmatch(r"[a-zA-Z0-9._-]{1,64}", value)
        ):
            result[key] = value
        elif (
            key == "session.id"
            and isinstance(value, str)
            and re.fullmatch(r"[0-9a-f]{64}", value)
        ):
            result[key] = value
        elif key.startswith(
            ("langfuse.observation.metadata.", "langfuse.trace.metadata.")
        ):
            field = key.rsplit(".", 1)[1]
            if field in COUNTERS and isinstance(value, str) and len(value) < 32:
                try:
                    value = float(value)
                except ValueError:
                    continue
            if (
                field in COUNTERS
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
                and value >= 0
            ):
                result[key] = value
            elif field == "outcome" and value in OUTCOMES:
                result[key] = value
            elif (
                field
                in {
                    "run_id",
                    "revision",
                    "prompt_revision",
                    "dataset_revision",
                    "embedding_revision",
                }
                and isinstance(value, str)
                and re.fullmatch(r"[a-zA-Z0-9._-]{1,200}", value)
            ):
                result[key] = value
        elif (
            key == "langfuse.observation.model.name"
            and isinstance(value, str)
            and re.fullmatch(r"[a-zA-Z0-9._:/-]{1,100}", value)
        ):
            result[key] = value
        elif key == "langfuse.observation.usage_details":
            import json

            try:
                usage = json.loads(value)
                if set(usage) <= {"input", "output", "total"} and all(
                    isinstance(v, int) and v >= 0 for v in usage.values()
                ):
                    result[key] = json.dumps(usage)
            except (ValueError, TypeError):
                pass
    return result


def sanitized_span(span: Any) -> Any | None:
    # Lazy SDK imports are confined to the adapter and explicit export path.
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.sdk.util.instrumentation import InstrumentationScope
    from opentelemetry.trace import Status, StatusCode

    if span.name not in NAMES:
        return None
    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=None if span.name == "recommend-food" else span.parent,
        start_time=span.start_time,
        end_time=span.end_time,
        attributes=safe_attributes(span.attributes),
        events=(),
        links=(),
        resource=Resource({}),
        instrumentation_scope=InstrumentationScope("langfuse", "4.16.0"),
        status=Status(StatusCode.UNSET),
    )
