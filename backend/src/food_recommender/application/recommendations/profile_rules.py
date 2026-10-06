"""Explicit corrections and monotonic restriction merging, outside inference."""

import re
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


def supported_addition(evidence: str, constraint: Constraint, message: str) -> bool:
    text = evidence.casefold()
    value = constraint_key(constraint)[1]
    names = {
        value,
        constraint.value.casefold(),
        *(alias for alias, canonical in ALIASES.items() if canonical == value),
    }
    if (
        value in {"none", "unknown", "null", "no allergies", "no restrictions"}
        or text not in message.casefold()
    ):
        return False
    if not any(
        re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text) for name in names
    ):
        return False
    if constraint.strength != Strength.HARD:
        return True
    if explicit_removal(evidence, constraint, message):
        return False
    if re.search(r"\b(?:not|no)\b.{0,20}\ballerg(?:y|ies|ic)\b", text):
        return False
    if re.search(
        r"\b(?:allerg(?:y|ies|ic)|avoid|exclude|strict(?:ly)?|never|no|without|free|intoleran(?:t|ce)|must|only)\b",
        text,
    ):
        return True
    return constraint.kind == ConstraintKind.DIETARY and bool(
        re.search(r"\bi(?: am|'m|’m)\b", text)
    )
