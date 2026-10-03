"""Independent read-only culinary MCP server."""

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from food_recommender.application.services import Services
from food_recommender.composition import build_mcp_services
from food_recommender.infrastructure.health import health_payload
from food_recommender.infrastructure.http import ObservedHTTP
from food_recommender.infrastructure.mcp_config import MCPSettings as MCPSettings
from food_recommender.infrastructure.observability import Runtime, configure_logging
from food_recommender.mcp.tools import register_lookups


def create_app(
    settings: MCPSettings | None = None,
    *,
    services: Services | None = None,
    runtime: Runtime | None = None,
) -> Starlette:
    settings = settings if settings is not None else MCPSettings()
    services = services if services is not None else build_mcp_services(settings)
    runtime = runtime if runtime is not None else Runtime(logger=configure_logging())
    server = FastMCP("foodwise-ai")
    if services.lookups is not None:
        register_lookups(server, services.lookups)

    @server.custom_route("/health/live", methods=["GET"])
    async def live(request: Request) -> JSONResponse:
        return JSONResponse({"status": "alive"})

    @server.custom_route("/health/ready", methods=["GET"])
    async def ready(request: Request) -> JSONResponse:
        payload, status = health_payload(await services.readiness.check())
        return JSONResponse(payload, status_code=status)

    app = server.http_app(
        path="/mcp",
        allowed_hosts=["mcp:8001", "localhost:8001", "127.0.0.1:8001"],
        allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    )
    app.add_middleware(ObservedHTTP, runtime=runtime)
    return app
