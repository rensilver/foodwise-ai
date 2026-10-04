"""Schema validation over an injected inference boundary; no provider SDK."""

import json
from typing import Any

from pydantic import TypeAdapter
from pydantic_core import to_jsonable_python

from food_recommender.application.contracts import contract_json_schema
from food_recommender.application.inference import Inference


async def structured[T](
    inference: Inference, prompt: str, context: Any, adapter: TypeAdapter[T]
) -> T:
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": json.dumps(to_jsonable_python(context), ensure_ascii=False),
        },
    ]
    content = await inference.generate(messages, contract_json_schema(adapter))
    return adapter.validate_json(content)
