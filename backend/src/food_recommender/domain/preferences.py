"""Preference provenance is separate from restriction strength."""

from dataclasses import dataclass

from food_recommender.domain.values import (
    ConstraintKind,
    Origin,
    Strength,
    nonempty,
    unique,
)


@dataclass(frozen=True)
class Constraint:
    kind: ConstraintKind
    value: str
    strength: Strength
    origin: Origin

    def __post_init__(self) -> None:
        nonempty(self.value)
        if self.strength == Strength.HARD and self.origin != Origin.EXPLICIT:
            raise ValueError("Hard constraints require explicit user evidence")


@dataclass(frozen=True)
class Preferences:
    cuisines: tuple[str, ...] = ()
    flavors: tuple[str, ...] = ()
    constraints: tuple[Constraint, ...] = ()
    location: str | None = None
    price_band: int | None = None

    def __post_init__(self) -> None:
        for values in (self.cuisines, self.flavors):
            unique(values)
            for value in values:
                nonempty(value)
        unique(self.constraints)
        if self.location is not None:
            nonempty(self.location)
        if self.price_band is not None and (
            type(self.price_band) is not int or not 1 <= self.price_band <= 4
        ):
            raise ValueError(
                "Price band must be unknown or an integer from one to four"
            )
