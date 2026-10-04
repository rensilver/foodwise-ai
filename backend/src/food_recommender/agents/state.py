"""JSON-only checkpoint state; branch results use independent replacement channels."""

import operator
from typing import Annotated, Any, TypedDict

from pydantic import ConfigDict, TypeAdapter

from food_recommender.retrieval.late_fusion import FusedCandidate

type CatalogContract = tuple[FusedCandidate, ...]
CATALOG_ADAPTER: TypeAdapter[tuple[FusedCandidate, ...]] = TypeAdapter(
    CatalogContract, config=ConfigDict(extra="forbid", strict=True)
)


class GraphState(TypedDict, total=False):
    request: dict[str, Any]
    conversation_id: str
    session_id: str
    run_id: str
    messages: Annotated[list[str], operator.add]
    profile: dict[str, Any] | None
    profile_outcome: dict[str, Any] | None
    retrieval: dict[str, Any] | None
    catalog: list[dict[str, Any]]
    trend: dict[str, Any] | None
    style: dict[str, Any] | None
    nutrition: dict[str, Any] | None
    final: dict[str, Any] | None
    errors: list[dict[str, Any]]
