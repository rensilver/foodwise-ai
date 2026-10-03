"""Application-configured connection; discovered schemas cannot grant capabilities."""

from types import TracebackType
from typing import Any, Literal
from uuid import UUID

from fastmcp import Client
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema import ValidationError as SchemaError
from pydantic import BaseModel, TypeAdapter, ValidationError

from food_recommender.application.contracts import multimodal_adapter
from food_recommender.application.lookups import (
    LookupResult,
    RestaurantMatch,
    ReviewMatch,
)
from food_recommender.application.trends import TrendRequest, TrendResult
from food_recommender.mcp.schemas import ImageRequest, SearchRequest

RAG_TOOLS = frozenset(
    {
        "get_restaurant_info",
        "recommend_by_vibe",
        "get_review",
        "search_restaurants",
        "search_recipes",
        "search_images",
    }
)
ALLOWLISTS = {
    "profile": frozenset(),
    "rag": RAG_TOOLS,
    "trend": frozenset({"search_food_trends"}),
    "style": frozenset(),
    "nutrition": frozenset(),
    "recommendation": frozenset(),
}
OUTPUTS: dict[str, TypeAdapter[Any]] = {
    "search_food_trends": TypeAdapter(TrendResult),
    "get_restaurant_info": TypeAdapter(LookupResult[RestaurantMatch]),
    "recommend_by_vibe": TypeAdapter(LookupResult[RestaurantMatch]),
    "get_review": TypeAdapter(LookupResult[ReviewMatch]),
    **{
        name: multimodal_adapter
        for name in ("search_restaurants", "search_recipes", "search_images")
    },
}


class ToolPolicyError(ValueError):
    """Safe boundary diagnostic, never includes supplied arguments/results."""


class AgentMCP:
    def __init__(
        self,
        client: Client[Any],
        role: Literal[
            "profile", "rag", "trend", "style", "nutrition", "recommendation"
        ],
        *,
        session_id: UUID | None = None,
        demo_profile_id: str | None = None,
        run_id: UUID | None = None,
    ) -> None:
        if role not in ALLOWLISTS:
            raise ToolPolicyError("Unknown agent role")
        self.client, self.role = client, role
        self.session_id, self.demo_profile_id, self.run_id = (
            session_id,
            demo_profile_id,
            run_id,
        )
        self.schemas: dict[str, dict[str, Any]] = {}

    async def __aenter__(self) -> "AgentMCP":
        await self.client.__aenter__()  # type: ignore[no-untyped-call]
        try:
            tools = await self.client.list_tools()
            self.schemas = {
                tool.name: tool.input_schema
                for tool in tools
                if tool.name in ALLOWLISTS[self.role]
            }
            return self
        except BaseException:
            await self.client.__aexit__(None, None, None)  # type: ignore[no-untyped-call]
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.schemas.clear()
        await self.client.__aexit__(exc_type, exc, traceback)  # type: ignore[no-untyped-call]

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self.schemas or name not in OUTPUTS:
            raise ToolPolicyError("Tool is unavailable or prohibited for this agent")
        arguments = dict(arguments)
        request_model: type[BaseModel] | None = None
        if name.startswith("search_") and name != "search_food_trends":
            request = dict(arguments.get("request", {}))
            if request.get("demo_profile_id") not in (None, self.demo_profile_id):
                raise ToolPolicyError("Review scope mismatch")
            request["demo_profile_id"] = self.demo_profile_id
            if name == "search_images":
                if request.get("session_id") not in (None, str(self.session_id)):
                    raise ToolPolicyError("Media scope mismatch")
                request["session_id"] = (
                    str(self.session_id) if self.session_id else None
                )
            arguments["request"] = request
            request_model = ImageRequest if name == "search_images" else SearchRequest
        if name == "search_food_trends":
            if self.run_id is None:
                raise ToolPolicyError("Application run ID is required")
            request = dict(arguments.get("request", {}))
            request["run_id"] = str(self.run_id)
            arguments["request"] = request
            request_model = TrendRequest
        if name == "get_review":
            if (
                self.demo_profile_id is None
                or arguments.get("demo_profile_id") != self.demo_profile_id
            ):
                raise ToolPolicyError("Review scope mismatch")
        try:
            Draft202012Validator(
                self.schemas[name], format_checker=Draft202012Validator.FORMAT_CHECKER
            ).validate(arguments)
            if request_model is not None:
                request_model.model_validate(arguments["request"])
        except (SchemaError, ValidationError, TypeError, ValueError):
            raise ToolPolicyError("Invalid tool arguments") from None
        result = await self.client.call_tool(name, arguments, timeout=30)
        if result.is_error or result.structured_content is None:
            raise ToolPolicyError("Invalid tool result")
        try:
            adapter = OUTPUTS[name]
            import json

            return adapter.validate_json(json.dumps(result.structured_content))
        except (ValidationError, ValueError, TypeError):
            raise ToolPolicyError("Invalid tool result") from None
