import type { Schema } from "../../lib/api/client";
export type Draft = Partial<
  Record<
    keyof Schema["RestaurantFields"] | keyof Schema["RecipeFields"],
    string
  >
>;
const common = [
  { key: "name", label: "Name" },
  { key: "cuisine", label: "Cuisine" },
] as const;
const restaurants = [
  { key: "location", label: "Location" },
  { key: "restaurant_type", label: "Restaurant type" },
  { key: "rating", label: "Dataset rating (0–5)", numeric: true },
  { key: "price_band", label: "Source price band (1–4)", numeric: true },
  { key: "signatures", label: "Signature dishes (one per line)", lines: true },
  { key: "vibe", label: "Ambiance" },
  { key: "environment", label: "Environment" },
  {
    key: "shortcomings",
    label: "Source limitations (one per line)",
    lines: true,
  },
] as const;
const recipes = [
  { key: "servings", label: "Servings", numeric: true },
  { key: "prep_time", label: "Preparation time (source string)" },
  { key: "cook_time", label: "Cooking time (source string)" },
  { key: "total_time", label: "Total time (source string)" },
  { key: "ingredients", label: "Ingredients (one per line)", lines: true },
  { key: "directions", label: "Directions (one per line)", lines: true },
] as const;
export function draftFromFields(
  fields: Schema["CatalogDetail"]["data"] | Record<string, unknown>,
): Draft {
  const draft: Draft = {};
  for (const field of [...common, ...restaurants, ...recipes]) {
    const value = (fields as Record<string, unknown>)[field.key];
    if (value != null)
      draft[field.key] = Array.isArray(value)
        ? value.join("\n")
        : String(value);
  }
  return draft;
}
const text = (value?: string) => value?.trim() || null;
const number = (value?: string) => (text(value) ? Number(value) : null);
const lines = (value?: string) =>
  text(value)
    ? value!
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
    : null;
export function restaurantFields(draft: Draft): Schema["RestaurantFields"] {
  return {
    name: draft.name?.trim() || "",
    cuisine: text(draft.cuisine),
    location: text(draft.location),
    restaurant_type: text(draft.restaurant_type),
    rating: number(draft.rating),
    price_band: number(draft.price_band),
    signatures: lines(draft.signatures),
    vibe: text(draft.vibe),
    environment: text(draft.environment),
    shortcomings: lines(draft.shortcomings),
  };
}
export function recipeFields(draft: Draft): Schema["RecipeFields"] {
  return {
    name: draft.name?.trim() || "",
    cuisine: text(draft.cuisine),
    servings: number(draft.servings),
    prep_time: text(draft.prep_time),
    cook_time: text(draft.cook_time),
    total_time: text(draft.total_time),
    ingredients: lines(draft.ingredients),
    directions: lines(draft.directions),
  };
}
export function CatalogEditor({
  category,
  draft,
  onChange,
  disabled,
}: {
  category: Schema["Category"];
  draft: Draft;
  onChange: (draft: Draft) => void;
  disabled: boolean;
}) {
  return (
    <fieldset
      disabled={disabled}
      className="editor-fields"
      style={{ border: 0, padding: 0 }}
    >
      <legend>Review catalog fields</legend>
      <p className="note">
        Leave unsupported facts blank. Saving validates fields and updates the
        searchable catalog.
      </p>
      {[...common, ...(category === "restaurant" ? restaurants : recipes)].map(
        (field) => (
          <label
            key={field.key}
            className={"lines" in field ? "wide-field" : undefined}
          >
            {field.label}
            {"lines" in field ? (
              <textarea
                rows={4}
                value={draft[field.key] ?? ""}
                onChange={(e) =>
                  onChange({ ...draft, [field.key]: e.target.value })
                }
              />
            ) : (
              <input
                type={"numeric" in field ? "number" : "text"}
                min={field.key === "rating" ? 0 : 1}
                max={
                  field.key === "rating"
                    ? 5
                    : field.key === "price_band"
                      ? 4
                      : undefined
                }
                step={field.key === "rating" ? ".1" : 1}
                required={field.key === "name"}
                maxLength={field.key === "name" ? 500 : undefined}
                value={draft[field.key] ?? ""}
                onChange={(e) =>
                  onChange({ ...draft, [field.key]: e.target.value })
                }
              />
            )}
          </label>
        ),
      )}
    </fieldset>
  );
}
