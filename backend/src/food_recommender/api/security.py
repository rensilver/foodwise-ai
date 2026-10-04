"""Browser origin checks and separate administrator/CSRF dependencies."""

from typing import Annotated

from fastapi import Depends, Request

from food_recommender.api.dependencies import get_services
from food_recommender.application.admin import AdminService
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.services import Services

ADMIN_COOKIE = "foodwise_admin"


def check_origin(request: Request, *, required: bool = False) -> None:
    origin = request.headers.get("origin")
    if (
        (required and not origin)
        or (origin is not None and origin not in request.app.state.allowed_origins)
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise ApplicationError(ErrorCode.FORBIDDEN)


async def safe_browser_write(request: Request) -> None:
    check_origin(request)


def admin_service(services: Annotated[Services, Depends(get_services)]) -> AdminService:
    if services.admin is None:
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return services.admin


async def administrator(
    request: Request, service: Annotated[AdminService, Depends(admin_service)]
) -> None:
    check_origin(request, required=True)
    await service.authorize(
        request.cookies.get(ADMIN_COOKIE), request.headers.get("x-csrf-token")
    )
