"""Configured local administrator login/logout only."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from food_recommender.api.security import (
    ADMIN_COOKIE,
    admin_service,
    administrator,
    check_origin,
)
from food_recommender.application.admin import AdminService

router = APIRouter(prefix="/api/v1/admin/session", tags=["admin"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    password: SecretStr = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    csrf_token: str
    expires_at: datetime


@router.post("", status_code=201, response_model=LoginResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AdminService, Depends(admin_service)],
) -> LoginResponse:
    check_origin(request, required=True)
    grant = await service.login(
        body.password.get_secret_value(), request.cookies.get(ADMIN_COOKIE)
    )
    response.set_cookie(
        ADMIN_COOKIE,
        grant.token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        path="/api/v1/admin",
        max_age=8 * 3600,
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(csrf_token=grant.csrf_token, expires_at=grant.expires_at)


@router.delete("", status_code=204, dependencies=[Depends(administrator)])
async def logout(
    request: Request, service: Annotated[AdminService, Depends(admin_service)]
) -> Response:
    await service.logout(request.cookies[ADMIN_COOKIE])
    response = Response(status_code=204)
    response.delete_cookie(
        ADMIN_COOKIE, path="/api/v1/admin", httponly=True, samesite="strict"
    )
    return response
