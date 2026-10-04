"""Explicit corrections and monotonic restriction merging, outside inference."""

from collections.abc import Iterable
from dataclasses import replace

from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import ConstraintKind, Origin, Strength
from food_recommender.retrieval.dietary import ALIASES


def constraint_key(constraint: Constraint) -> tuple[ConstraintKind, str]:
    value = constraint.value.casefold().strip()
    return constraint.kind, ALIASES.get(value, value)


def merge_constraints(
    prior: tuple[Constraint, ...],
    additions: Iterable[Constraint],
    removals: set[tuple[ConstraintKind, str]],
) -> tuple[Constraint, ...]:
    result = {constraint_key(c): c for c in prior if constraint_key(c) not in removals}
    for constraint in additions:
        key = constraint_key(constraint)
        known = result.get(key)
        if known and (
            known.strength == Strength.HARD
            or (
                known.origin == Origin.EXPLICIT and constraint.origin == Origin.INFERRED
            )
        ):
            continue
        result[key] = replace(constraint, value=key[1])
    return tuple(result[key] for key in sorted(result))


def explicit_removal(evidence: str, constraint: Constraint, message: str) -> bool:
    return (
        evidence.casefold() in message.casefold()
        and constraint.value.casefold() in evidence.casefold()
        and any(
            marker in evidence.casefold()
            for marker in (
                "no longer",
                "remove",
                "not allergic",
                "can eat",
                "don't need",
                "do not need",
                "not strict",
            )
        )
    )
