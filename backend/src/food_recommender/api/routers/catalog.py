"""Catalog browse routes with distinct restaurant and recipe query contracts."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from food_recommender.api.dependencies import get_services
from food_recommender.api.schemas import Identity
from food_recommender.application.catalog.browse import (
    BrowseService,
    CatalogDetail,
    CatalogPage,
    RecipeFilters,
    RestaurantFilters,
)
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.services import Services
from food_recommender.domain.values import Category, EntityRef

router = APIRouter(prefix="/api/v1", tags=["catalog"])


def browse(services: Annotated[Services, Depends(get_services)]) -> BrowseService:
    if services.browse is None:
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return services.browse


Service = Annotated[BrowseService, Depends(browse)]


@router.get("/restaurants", response_model=CatalogPage)
async def restaurants(
    filters: Annotated[RestaurantFilters, Query()], service: Service
) -> CatalogPage:
    return await service.list(Category.RESTAURANT, filters)


@router.get("/recipes", response_model=CatalogPage)
async def recipes(
    filters: Annotated[RecipeFilters, Query()], service: Service
) -> CatalogPage:
    return await service.list(Category.RECIPE, filters)


@router.get("/restaurants/{entity_id}", response_model=CatalogDetail)
async def restaurant(entity_id: Identity, service: Service) -> CatalogDetail:
    return await service.detail(EntityRef(Category.RESTAURANT, entity_id))


@router.get("/recipes/{entity_id}", response_model=CatalogDetail)
async def recipe(entity_id: Identity, service: Service) -> CatalogDetail:
    return await service.detail(EntityRef(Category.RECIPE, entity_id))
