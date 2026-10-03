"""Pydantic boundary adapters over the framework-independent domain contracts.

JSON schemas are generated from the same types used by the application. Future
HTTP/MCP/provider boundaries can reuse these without copying domain fields.
"""

from typing import Annotated

from pydantic import ConfigDict, Field, TypeAdapter
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema

from food_recommender.domain.events import ProgressEvents
from food_recommender.domain.experts import (
    ExpertOutcome,
    NutritionAnalysis,
    ProfileResult,
    RetrievalResult,
    StyleAnalysis,
    TrendAnalysis,
)
from food_recommender.domain.preferences import Preferences
from food_recommender.domain.recommendations import RecommendationResult
from food_recommender.retrieval.outcomes import TextRetrievalOutcome

_CONFIG = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class ContractSchema(GenerateJsonSchema):
    """Reflect extra-field rejection for nested stdlib dataclasses in JSON Schema."""

    def dataclass_schema(self, schema: core_schema.DataclassSchema) -> JsonSchemaValue:
        result = super().dataclass_schema(schema)
        result["additionalProperties"] = False
        return result


def contract_json_schema[T](adapter: TypeAdapter[T]) -> JsonSchemaValue:
    return adapter.json_schema(schema_generator=ContractSchema)


# The named alias lets boundary configuration propagate to stdlib dataclasses.
type ProfileContract = ProfileResult
profile_adapter: TypeAdapter[ProfileResult] = TypeAdapter(
    ProfileContract, config=_CONFIG
)
event_adapter: TypeAdapter[ProgressEvents] = TypeAdapter(
    Annotated[ProgressEvents, Field(discriminator="event")], config=_CONFIG
)
profile_outcome_adapter: TypeAdapter[ExpertOutcome[ProfileResult]] = TypeAdapter(
    Annotated[ExpertOutcome[ProfileResult], Field(discriminator="status")],
    config=_CONFIG,
)
retrieval_outcome_adapter: TypeAdapter[ExpertOutcome[RetrievalResult]] = TypeAdapter(
    Annotated[ExpertOutcome[RetrievalResult], Field(discriminator="status")],
    config=_CONFIG,
)
trend_outcome_adapter: TypeAdapter[ExpertOutcome[TrendAnalysis]] = TypeAdapter(
    Annotated[ExpertOutcome[TrendAnalysis], Field(discriminator="status")],
    config=_CONFIG,
)
style_outcome_adapter: TypeAdapter[ExpertOutcome[StyleAnalysis]] = TypeAdapter(
    Annotated[ExpertOutcome[StyleAnalysis], Field(discriminator="status")],
    config=_CONFIG,
)
nutrition_outcome_adapter: TypeAdapter[ExpertOutcome[NutritionAnalysis]] = TypeAdapter(
    Annotated[ExpertOutcome[NutritionAnalysis], Field(discriminator="status")],
    config=_CONFIG,
)
recommendation_outcome_adapter: TypeAdapter[ExpertOutcome[RecommendationResult]] = (
    TypeAdapter(
        Annotated[ExpertOutcome[RecommendationResult], Field(discriminator="status")],
        config=_CONFIG,
    )
)


type PreferencesContract = Preferences
preferences_adapter: TypeAdapter[Preferences] = TypeAdapter(
    PreferencesContract, config=_CONFIG
)


type TextRetrievalContract = TextRetrievalOutcome
text_retrieval_adapter: TypeAdapter[TextRetrievalOutcome] = TypeAdapter(
    TextRetrievalContract, config=_CONFIG
)
