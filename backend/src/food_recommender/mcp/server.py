"""Independent read-only culinary MCP server."""

from argparse import ArgumentParser
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from food_recommender.application.services import Services
from food_recommender.application.trends.service import TrendService
from food_recommender.composition import build_mcp_services
from food_recommender.infrastructure.health import health_payload
from food_recommender.infrastructure.mcp_config import MCPSettings as MCPSettings
from food_recommender.infrastructure.observability import Runtime, configure_logging
from food_recommender.mcp.resources import register_resources
from food_recommender.mcp.tools import (
    register_lookups,
    register_search,
    register_trends,
)
from food_recommender.retrieval.multimodal import MultimodalRetrieval
from food_recommender.transport.http import ObservedHTTP


def create_server(
    settings: MCPSettings | None = None,
    *,
    services: Services | None = None,
    runtime: Runtime | None = None,
) -> FastMCP:
    settings = settings if settings is not None else MCPSettings()
    services = services if services is not None else build_mcp_services(settings)
    runtime = runtime if runtime is not None else Runtime(logger=configure_logging())

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if services.close is not None:
                await services.close()

    server = FastMCP("foodwise-ai", lifespan=lifespan, mask_error_details=True)
    if services.lookups is not None:
        register_lookups(server, services.lookups)
    if services.resources is not None:
        register_resources(server, services.resources)
    register_trends(server, services.trends or TrendService(None))
    register_search(server, services.retrieval or MultimodalRetrieval(None, None))

    @server.custom_route("/health/live", methods=["GET"])
    async def live(request: Request) -> JSONResponse:
        return JSONResponse({"status": "alive"})

    @server.custom_route("/health/ready", methods=["GET"])
    async def ready(request: Request) -> JSONResponse:
        payload, status = health_payload(await services.readiness.check())
        return JSONResponse(payload, status_code=status)

    return server


def create_app(
    settings: MCPSettings | None = None,
    *,
    services: Services | None = None,
    runtime: Runtime | None = None,
) -> Starlette:
    runtime = runtime if runtime is not None else Runtime(logger=configure_logging())
    server = create_server(settings, services=services, runtime=runtime)
    app = server.http_app(
        path="/mcp",
        allowed_hosts=["mcp:8001", "localhost:8001", "127.0.0.1:8001"],
        allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    )
    app.add_middleware(ObservedHTTP, runtime=runtime)
    return app


def main() -> None:
    parser = ArgumentParser(description="Read-only foodwise-ai MCP server")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    configure_logging()
    settings = MCPSettings(_env_file=args.env_file)
    if args.transport == "stdio":
        server = create_server(settings)
        server.run(transport="stdio", show_banner=False)
    else:
        import uvicorn

        uvicorn.run(create_app(settings), host="127.0.0.1", port=8001, access_log=False)


if __name__ == "__main__":
    main()
