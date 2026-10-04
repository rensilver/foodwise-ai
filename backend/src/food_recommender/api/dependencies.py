"""FastAPI dependency access; replace providers through dependency_overrides."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import Depends, Request, Response

from food_recommender.application.conversations import ConversationService
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.services import Services


def get_services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


SESSION_COOKIE = "foodwise_session"


def conversations(
    services: Annotated[Services, Depends(get_services)],
) -> ConversationService:
    if services.conversations is None:
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return services.conversations


async def browser_session(
    request: Request, service: Annotated[ConversationService, Depends(conversations)]
) -> UUID:
    identity, _ = await service.session(request.cookies.get(SESSION_COOKIE))
    return identity


async def create_browser_session(
    request: Request,
    response: Response,
    service: Annotated[ConversationService, Depends(conversations)],
) -> UUID:
    identity, token = await service.session(
        request.cookies.get(SESSION_COOKIE), create=True
    )
    if token:
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/",
            max_age=60 * 60 * 24 * 30,
        )
    return identity
