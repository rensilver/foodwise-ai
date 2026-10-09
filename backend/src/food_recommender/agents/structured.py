"""Schema validation over an injected inference boundary; no provider SDK."""

import json
from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter, ValidationError
from pydantic_core import to_jsonable_python

from food_recommender.application.recommendations.contracts import contract_json_schema
from food_recommender.application.recommendations.inference import (
    Inference,
    InferenceError,
)
from food_recommender.application.recommendations.reliability import current_budget


class GroundingError(ValueError):
    """Trusted repair instructions, authored by validators, never source text."""


def schema_feedback(error: ValidationError) -> str:
    """Describe field locations/types without echoing inputs or exception messages."""
    return (
        "Previous response failed schema validation. Return only valid JSON matching "
        "the schema; collection fields must be JSON arrays, not objects or strings. "
        "Do not add fields or facts. Field errors: "
        + json.dumps(
            [
                {"location": issue["loc"], "type": issue["type"]}
                for issue in error.errors(include_input=False, include_url=False)[:10]
            ]
        )
    )


async def structured[T](
    inference: Inference,
    prompt: str,
    context: Any,
    adapter: TypeAdapter[T],
    *,
    repairs: int | None = None,
    validate: Callable[[T], None] | None = None,
) -> T:
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps(to_jsonable_python(context), ensure_ascii=False),
        },
    ]
    budget = current_budget.get()
    allowed = (
        repairs
        if repairs is not None
        else budget.limits.schema_repairs
        if budget
        else 0
    )
    for attempt in range(allowed + 1):
        if budget:
            budget.remaining()
        try:
            content = await inference.generate(messages, contract_json_schema(adapter))
            result = adapter.validate_json(content)
            if validate is not None:
                try:
                    validate(result)
                except GroundingError:
                    raise
                except ValueError:
                    raise GroundingError() from None
            return result
        except (ValidationError, InferenceError, GroundingError) as error:
            if isinstance(error, InferenceError) and not error.schema_error:
                raise
            if attempt == allowed:
                raise
            if isinstance(error, GroundingError):
                messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        (
                            str(error)
                            or "Previous response failed evidence validation. Use only supplied entity IDs and supported citation IDs. Copy a short contiguous source substring exactly, including Markdown and punctuation; the quotation itself must support the assessment. Do not paraphrase or add facts."
                        )
                        if isinstance(error, GroundingError)
                        else schema_feedback(error)
                        if isinstance(error, ValidationError)
                        else "Previous response failed schema validation. Return only valid JSON matching the schema; do not add fields or facts."
                    ),
                }
            )
    raise InferenceError(schema_error=True)
