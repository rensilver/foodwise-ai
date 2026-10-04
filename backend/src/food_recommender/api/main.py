"""FastAPI startup scaffold; recommendation routes arrive in later phases."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from food_recommender.api.body_limits import BodyLimits
from food_recommender.api.dependencies import get_services
from food_recommender.api.routers.admin_catalog import router as admin_catalog_router
from food_recommender.api.routers.admin_session import router as admin_session_router
from food_recommender.api.routers.catalog import router as catalog_router
from food_recommender.api.routers.conversations import router as conversation_router
from food_recommender.api.routers.media import router as media_router
from food_recommender.api.security import safe_browser_write
from food_recommender.application.errors import ErrorCode
from food_recommender.application.services import Services
from food_recommender.composition import build_backend_services
from food_recommender.infrastructure.config import Settings, load_settings
from food_recommender.infrastructure.health import backend_readiness, health_payload
from food_recommender.infrastructure.observability import Runtime, configure_logging
from food_recommender.transport.http import ErrorEnvelope, ObservedHTTP, error_response


def create_app(
    settings: Settings | None = None,
    *,
    probe: Callable[[Settings], Awaitable[dict[str, bool]]] = backend_readiness,
    services: Services | None = None,
    runtime: Runtime | None = None,
) -> FastAPI:
    settings = settings if settings is not None else load_settings()
    services = (
        services
        if services is not None
        else build_backend_services(settings, probe=probe)
    )
    runtime = runtime if runtime is not None else Runtime(logger=configure_logging())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if services.close is not None:
                await services.close()

    app = FastAPI(title="foodwise-ai", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.services = services
    app.state.allowed_origins = settings.allowed_origins
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "backend"]
    )
    app.add_middleware(BodyLimits)
    app.add_middleware(ObservedHTTP, runtime=runtime)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        return error_response(ErrorCode.INVALID_REQUEST)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        code = {
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            503: ErrorCode.DEPENDENCY_UNAVAILABLE,
        }.get(
            error.status_code,
            ErrorCode.INVALID_REQUEST
            if error.status_code < 500
            else ErrorCode.INTERNAL_ERROR,
        )
        return error_response(code, status=error.status_code)

    @app.get("/api/v1/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready", responses={500: {"model": ErrorEnvelope}})
    async def ready(
        services: Annotated[Services, Depends(get_services)],
    ) -> JSONResponse:
        payload, status = health_payload(await services.readiness.check())
        return JSONResponse(payload, status_code=status)

    app.include_router(conversation_router, dependencies=[Depends(safe_browser_write)])
    app.include_router(catalog_router)
    app.include_router(media_router, dependencies=[Depends(safe_browser_write)])
    app.include_router(admin_session_router)
    app.include_router(admin_catalog_router)
    return app
