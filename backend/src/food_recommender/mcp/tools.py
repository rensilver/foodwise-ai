"""Typed read-only tools; application services own all behavior."""

from typing import Annotated

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from food_recommender.application.lookups import (
    LookupResult,
    LookupService,
    RestaurantMatch,
    ReviewMatch,
)

ShortText = Annotated[str, Field(min_length=1, max_length=200)]
Limit = Annotated[int, Field(ge=1, le=20, strict=True)]
READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, openWorldHint=False
)


def register_lookups(server: FastMCP, service: LookupService) -> None:
    @server.tool(annotations=READ_ONLY)
    async def get_restaurant_info(name: ShortText) -> LookupResult[RestaurantMatch]:
        """Exact case-insensitive name lookup; multiple IDs indicate ambiguity."""
        return await service.restaurant(name)

    @server.tool(annotations=READ_ONLY)
    async def recommend_by_vibe(
        vibe: ShortText, limit: Limit = 20
    ) -> LookupResult[RestaurantMatch]:
        """Search catalog ambiance and raw description, with a bounded result count."""
        return await service.vibe(vibe, limit)

    @server.tool(annotations=READ_ONLY)
    async def get_review(
        restaurant_id: ShortText, demo_profile_id: ShortText
    ) -> LookupResult[ReviewMatch]:
        """Return linked synthetic review evidence within an explicit demo scope."""
        return await service.review(restaurant_id, demo_profile_id)
