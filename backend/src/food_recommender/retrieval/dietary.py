"""Conservative deterministic checks over complete canonical ingredients.

The course catalog has no verified allergen-absence or cross-contact evidence.
Recognized simple plant ingredients can support a dietary composition claim;
compound/ambiguous ingredients and unimplemented diets stay unknown.
"""

import re
from dataclasses import dataclass

from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import ConstraintKind, EvidenceState, Strength

ALLERGENS = {
    "milk": (
        "milk",
        "cheese",
        "mozzarella",
        "parmesan",
        "butter",
        "cream",
        "yogurt",
        "whey",
        "casein",
        "ghee",
    ),
    "egg": ("egg", "eggs", "mayonnaise"),
    "peanut": ("peanut", "peanuts", "groundnut"),
    "tree nut": (
        "almond",
        "almonds",
        "walnut",
        "walnuts",
        "cashew",
        "cashews",
        "pecan",
        "pistachio",
        "hazelnut",
    ),
    "soy": ("soy", "soybean", "tofu", "tempeh", "edamame", "miso"),
    "wheat": ("wheat", "flour", "bread", "pasta", "semolina", "couscous"),
    "fish": ("fish", "salmon", "tuna", "cod", "anchovy", "anchovies", "sardine"),
    "shellfish": (
        "shrimp",
        "prawn",
        "crab",
        "lobster",
        "clam",
        "mussel",
        "oyster",
        "scallop",
    ),
    "sesame": ("sesame", "tahini"),
    "gluten": ("wheat", "barley", "rye", "flour", "bread", "pasta", "soy sauce"),
}
ALIASES = {
    "dairy": "milk",
    "eggs": "egg",
    "peanuts": "peanut",
    "tree nuts": "tree nut",
    "soybeans": "soy",
}
MEAT = (
    "chicken",
    "beef",
    "pork",
    "bacon",
    "ham",
    "lamb",
    "turkey",
    "duck",
    "gelatin",
    "lard",
    *ALLERGENS["fish"],
    *ALLERGENS["shellfish"],
)
PLANTS = {
    "tomato",
    "tomatoes",
    "rice",
    "salt",
    "water",
    "olive oil",
    "basil",
    "onion",
    "onions",
    "garlic",
    "carrot",
    "carrots",
    "potato",
    "potatoes",
    "lentils",
    "chickpeas",
    "spinach",
    "broccoli",
    "zucchini",
    "quinoa",
    "lemon juice",
    "black pepper",
}


@dataclass(frozen=True)
class DietaryAssessment:
    constraint: Constraint
    state: EvidenceState
    reason: str


def contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(
        re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text) for term in terms
    )


def assess(
    constraint: Constraint,
    ingredients: tuple[str, ...] | None,
    allergens: tuple[str, ...] | None,
) -> DietaryAssessment:
    value = constraint.value.casefold().strip()
    value = ALIASES.get(value, value)
    text = "\n".join((*(ingredients or ()), *(allergens or ()))).casefold()
    terms: tuple[str, ...] = ()
    if constraint.kind == ConstraintKind.ALLERGEN:
        terms = ALLERGENS.get(value, (value,))
    elif value in ("vegan", "vegetarian"):
        terms = MEAT + (
            (*ALLERGENS["milk"], *ALLERGENS["egg"], "honey") if value == "vegan" else ()
        )
    elif value in ("gluten-free", "gluten free"):
        terms = ALLERGENS["gluten"]
    if contains(text, terms):
        return DietaryAssessment(
            constraint,
            EvidenceState.CONFLICTING,
            "Canonical ingredients or declared allergens contain a conflict",
        )
    if (
        constraint.kind == ConstraintKind.DIETARY
        and value in ("vegan", "vegetarian")
        and ingredients
        and all(ingredient.casefold().strip() in PLANTS for ingredient in ingredients)
    ):
        return DietaryAssessment(
            constraint,
            EvidenceState.SUPPORTED,
            "Complete canonical ingredient list contains only recognized simple plant ingredients; no cross-contact claim",
        )
    return DietaryAssessment(
        constraint,
        EvidenceState.UNKNOWN,
        "Catalog lacks sufficient verified compliance evidence",
    )


def eligible(assessments: tuple[DietaryAssessment, ...]) -> bool:
    return all(
        a.constraint.strength != Strength.HARD or a.state == EvidenceState.SUPPORTED
        for a in assessments
    )
