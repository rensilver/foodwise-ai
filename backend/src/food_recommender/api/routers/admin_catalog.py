"""Explicit local admin catalog edits; preview never persists or auto-submits."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from food_recommender.api.dependencies import get_services
from food_recommender.api.routers.catalog import Identity
from food_recommender.api.security import administrator
from food_recommender.application.admin_catalog import (
    AdminCatalogService,
    RecipePatch,
    RestaurantPatch,
)
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.services import Services
from food_recommender.domain.catalog import CatalogSnapshot
from food_recommender.domain.values import Category, EntityRef
from food_recommender.ingestion.extraction import (
    ExtractionResult,
    RecipeFields,
    RestaurantFields,
)

router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(administrator)]
)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class PreviewRequest(Input):
    category: Category
    text: str = Field(min_length=1, max_length=65536, pattern=r"\S")


class RestaurantCreate(Input):
    fields: RestaurantFields


class RecipeCreate(Input):
    fields: RecipeFields


class RestaurantUpdate(Input):
    expected_version: int = Field(ge=1)
    fields: RestaurantPatch


class RecipeUpdate(Input):
    expected_version: int = Field(ge=1)
    fields: RecipePatch


class DeleteRequest(Input):
    expected_version: int = Field(ge=1)
    confirm_id: str = Field(min_length=1, max_length=200)


def admin_catalog(
    services: Annotated[Services, Depends(get_services)],
) -> AdminCatalogService:
    if services.admin_catalog is None:
        raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    return services.admin_catalog


Service = Annotated[AdminCatalogService, Depends(admin_catalog)]


@router.post("/extractions/preview", response_model=ExtractionResult)
async def preview(body: PreviewRequest, service: Service) -> ExtractionResult:
    return await service.preview(body.text, body.category)


@router.post("/restaurants", status_code=201, response_model=CatalogSnapshot)
async def create_restaurant(
    body: RestaurantCreate, service: Service
) -> CatalogSnapshot:
    return await service.create(Category.RESTAURANT, body.fields.model_dump())


@router.post("/recipes", status_code=201, response_model=CatalogSnapshot)
async def create_recipe(body: RecipeCreate, service: Service) -> CatalogSnapshot:
    return await service.create(Category.RECIPE, body.fields.model_dump())


@router.patch("/restaurants/{entity_id}", response_model=CatalogSnapshot)
async def update_restaurant(
    entity_id: Identity, body: RestaurantUpdate, service: Service
) -> CatalogSnapshot:
    return await service.update(
        EntityRef(Category.RESTAURANT, entity_id),
        body.fields.model_dump(exclude_unset=True),
        body.expected_version,
    )


@router.patch("/recipes/{entity_id}", response_model=CatalogSnapshot)
async def update_recipe(
    entity_id: Identity, body: RecipeUpdate, service: Service
) -> CatalogSnapshot:
    return await service.update(
        EntityRef(Category.RECIPE, entity_id),
        body.fields.model_dump(exclude_unset=True),
        body.expected_version,
    )


@router.delete("/restaurants/{entity_id}", status_code=204)
async def delete_restaurant(
    entity_id: Identity, body: DeleteRequest, service: Service
) -> Response:
    await service.delete(
        EntityRef(Category.RESTAURANT, entity_id),
        body.expected_version,
        body.confirm_id,
    )
    return Response(status_code=204)


@router.delete("/recipes/{entity_id}", status_code=204)
async def delete_recipe(
    entity_id: Identity, body: DeleteRequest, service: Service
) -> Response:
    await service.delete(
        EntityRef(Category.RECIPE, entity_id), body.expected_version, body.confirm_id
    )
    return Response(status_code=204)
