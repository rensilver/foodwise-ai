import pytest

from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import (
    ConstraintKind,
    EvidenceState,
    Origin,
    Strength,
)
from food_recommender.retrieval.dietary import assess, eligible


def restriction(value="milk", kind=ConstraintKind.ALLERGEN, strength=Strength.HARD):
    return Constraint(kind, value, strength, Origin.EXPLICIT)


@pytest.mark.parametrize("ingredients", [None, (), ("tomato",), ("mystery sauce",)])
def test_allergen_absence_without_verified_evidence_is_unknown(ingredients):
    result = assess(restriction(), ingredients, ())
    assert result.state == EvidenceState.UNKNOWN
    assert not eligible((result,))


@pytest.mark.parametrize(
    "ingredient", ["milk", "2 cups mozzarella", "whey protein", "butter"]
)
def test_known_conflicts_override_empty_allergen_metadata(ingredient):
    assert assess(restriction(), (ingredient,), ()).state == EvidenceState.CONFLICTING


def test_strict_diet_supported_only_with_complete_understood_ingredients():
    vegan = restriction("vegan", ConstraintKind.DIETARY)
    assert (
        assess(vegan, ("tomato", "rice", "salt"), None).state == EvidenceState.SUPPORTED
    )
    assert (
        assess(vegan, ("tomato", "secret sauce"), None).state == EvidenceState.UNKNOWN
    )
    assert (
        assess(vegan, ("tomato", "chicken broth"), None).state
        == EvidenceState.CONFLICTING
    )
    assert assess(vegan, ("honey",), None).state == EvidenceState.CONFLICTING
    assert (
        assess(restriction("keto", ConstraintKind.DIETARY), ("rice",), None).state
        == EvidenceState.UNKNOWN
    )
    assert eligible((assess(restriction(strength=Strength.SOFT), ("milk",), None),))
