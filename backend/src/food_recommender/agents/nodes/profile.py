"""Structured profile extraction, application-owned review scope and typed failures."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from food_recommender.agents.prompts import PROFILE
from food_recommender.agents.structured import structured
from food_recommender.application.inference import Inference
from food_recommender.application.workflow import TurnRequest
from food_recommender.domain.experts import (
    AgentFailure,
    AgentSuccess,
    ExpertOutcome,
    ProfileResult,
)
from food_recommender.domain.preferences import Constraint, Preferences
from food_recommender.domain.values import Category


class ConstraintChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: Literal["add", "remove"]
    constraint: Constraint
    evidence: str = Field(min_length=1, max_length=2000)


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    categories: tuple[Category, ...] | None = Field(
        default=None, min_length=1, max_length=2
    )
    cuisines: tuple[str, ...] | None = None
    flavors: tuple[str, ...] | None = None
    location: str | None = None
    price_band: int | None = Field(default=None, ge=1, le=4)
    changes: tuple[ConstraintChange, ...] = Field(default=(), max_length=20)
    clarification: str | None = Field(default=None, min_length=1, max_length=1000)


class UserProfileGenerator:
    def __init__(self, inference: Inference) -> None:
        self.inference = inference

    async def run(
        self,
        request: TurnRequest,
        prior: ProfileResult | None = None,
        *,
        history: tuple[str, ...] = (),
        reviews: tuple[str, ...] = (),
    ) -> ExpertOutcome[ProfileResult]:
        try:
            patch = await structured(
                self.inference,
                PROFILE,
                {
                    "request": request,
                    "prior": prior,
                    "history": history,
                    "scoped_synthetic_reviews": reviews
                    if request.demo_profile_id
                    else (),
                },
                TypeAdapter(ProfilePatch),
            )
            return AgentSuccess(self.merge(request, patch, prior))
        except Exception:
            return AgentFailure("invalid_response")

    def merge(
        self, request: TurnRequest, patch: ProfilePatch, prior: ProfileResult | None
    ) -> ProfileResult:
        base = prior.preferences if prior else Preferences()
        explicit = request.explicit
        return ProfileResult(
            request.categories
            or patch.categories
            or (prior.categories if prior else (Category.RESTAURANT, Category.RECIPE)),
            Preferences(
                cuisines=explicit.cuisines
                if explicit.cuisines is not None
                else patch.cuisines
                if patch.cuisines is not None
                else base.cuisines,
                flavors=explicit.flavors
                if explicit.flavors is not None
                else patch.flavors
                if patch.flavors is not None
                else base.flavors,
                location=explicit.location
                if "location" in explicit.model_fields_set
                else patch.location or base.location,
                price_band=explicit.price_band
                if "price_band" in explicit.model_fields_set
                else patch.price_band or base.price_band,
                constraints=tuple(
                    dict.fromkeys(
                        (
                            *base.constraints,
                            *explicit.constraints,
                            *(
                                change.constraint
                                for change in patch.changes
                                if change.operation == "add"
                            ),
                        )
                    )
                ),
            ),
            patch.clarification,
        )
