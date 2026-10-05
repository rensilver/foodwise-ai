"""Schema validation over an injected inference boundary; no provider SDK."""

import json
from typing import Any

from pydantic import TypeAdapter, ValidationError
from pydantic_core import to_jsonable_python

from food_recommender.application.recommendations.contracts import contract_json_schema
from food_recommender.application.recommendations.inference import (
    Inference,
    InferenceError,
)
from food_recommender.application.recommendations.reliability import current_budget


async def structured[T](
    inference: Inference,
    prompt: str,
    context: Any,
    adapter: TypeAdapter[T],
    *,
    repairs: int | None = None,
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
            return adapter.validate_json(content)
        except (ValidationError, InferenceError) as error:
            if isinstance(error, InferenceError) and not error.schema_error:
                raise
            if attempt == allowed:
                raise
            messages.append(
                {
                    "role": "user",
                    "content": "Previous response failed schema validation. Return only valid JSON matching the schema; do not add fields or facts.",
                }
            )
    raise InferenceError(schema_error=True)
