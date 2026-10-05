"""Typed read-only tools; application services own all behavior."""

from typing import Annotated

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from food_recommender.application.catalog.lookups import (
    LookupResult,
    LookupService,
    RestaurantMatch,
    ReviewMatch,
)
from food_recommender.application.trends.service import (
    TrendRequest,
    TrendResult,
    TrendService,
)
from food_recommender.domain.values import Category
from food_recommender.mcp.schemas import ImageRequest, SearchRequest
from food_recommender.retrieval.multimodal import MultimodalOutcome, MultimodalRetrieval

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


def register_search(server: FastMCP, service: MultimodalRetrieval) -> None:
    @server.tool(annotations=READ_ONLY)
    async def search_restaurants(request: SearchRequest) -> MultimodalOutcome:
        """Constrained restaurant retrieval with source citations and component scores."""
        return await service.run(request.plan(Category.RESTAURANT), use_images=False)

    @server.tool(annotations=READ_ONLY)
    async def search_recipes(request: SearchRequest) -> MultimodalOutcome:
        """Constrained recipe retrieval; canonical ingredients support dietary checks."""
        return await service.run(request.plan(Category.RECIPE), use_images=False)

    @server.tool(annotations=READ_ONLY)
    async def search_images(request: ImageRequest) -> MultimodalOutcome:
        """CLIP text/image search using an authorized media ID and actual entity links."""
        return await service.run(
            request.plan(request.category),
            media_id=request.media_id,
            session_id=request.session_id,
            use_text=False,
        )


def register_trends(server: FastMCP, service: TrendService) -> None:
    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, destructiveHint=False, openWorldHint=True
        )
    )
    async def search_food_trends(request: TrendRequest) -> TrendResult:
        """Bounded public culinary trend search. Internal cache writes are permitted."""
        return await service.search(request)
