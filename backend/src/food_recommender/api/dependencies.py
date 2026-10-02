"""FastAPI dependency access; replace providers through dependency_overrides."""

from typing import cast

from fastapi import Request

from food_recommender.application.services import Services


def get_services(request: Request) -> Services:
    return cast(Services, request.app.state.services)
