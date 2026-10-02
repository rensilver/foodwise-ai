"""FastAPI startup scaffold; recommendation routes arrive in later phases."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from food_recommender.infrastructure.config import Settings, load_settings
from food_recommender.infrastructure.health import backend_readiness, health_payload


def create_app(
    settings: Settings | None = None,
    *,
    probe: Callable[[Settings], Awaitable[dict[str, bool]]] = backend_readiness,
) -> FastAPI:
    settings = settings if settings is not None else load_settings()
    app = FastAPI(title="foodwise-ai", docs_url=None, redoc_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "backend"]
    )

    @app.get("/api/v1/health/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready")
    async def ready() -> JSONResponse:
        payload, status = health_payload(await probe(settings))
        return JSONResponse(payload, status_code=status)

    return app
