"use client";
import Link from "next/link";
import type { Schema } from "../../lib/api/client";
import { Sources } from "./sources";
import {
  CatalogFacts,
  CatalogImage,
  RecipeIngredients,
  useCatalogDetail,
} from "./catalog-presentation";
export function Recommendations({
  event,
}: {
  event: Schema["RecommendationsEvent"];
}) {
  return (
    <section aria-label="Meal recommendations">
      {event.trend?.status !== "success" && (
        <p className="notice">Current trend information is unavailable.</p>
      )}
      {event.style && event.style.status !== "success" && (
        <p className="note">
          Food style analysis is unavailable. Retrieved facts remain visible.
        </p>
      )}
      {event.nutrition?.status !== "success" && (
        <p className="note">
          Dietary analysis is unavailable. Compliance is unknown.
        </p>
      )}
      {[...new Set(event.result.limitations)].map((limit, i) => (
        <p className="note" key={i}>
          {limit}
        </p>
      ))}
      {!event.result.recommendations.length && (
        <p className="notice">
          No supported matches. Edit the request or preferences; retained hard
          restrictions still apply.
        </p>
      )}
      <div className="results">
        {(["restaurant", "recipe"] as const).map((category) => {
          const items = event.result.recommendations.filter(
            (item) => item.entity.category === category,
          );
          if (!items.length) return null;
          return (
            <section
              key={category}
              aria-label={
                category === "restaurant" ? "Places to eat" : "Recipes to cook"
              }
            >
              <h2>
                {category === "restaurant"
                  ? "Places to eat"
                  : "Recipes to cook"}
              </h2>
              <div
                className={
                  category === "recipe" ? "recipe-grid" : "restaurant-list"
                }
              >
                {items.map((item) => (
                  <RecommendationItem
                    key={`${category}:${item.entity.id}`}
                    item={item}
                    event={event}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
      {event.trend?.status === "success" &&
        event.trend.result.claims.map((claim, i) => (
          <section key={i}>
            <h3>Current trend evidence</h3>
            <p>{claim.claim}</p>
            <Sources citations={claim.citations} />
          </section>
        ))}
    </section>
  );
}
function RecommendationItem({
  item,
  event,
}: {
  item: Schema["Recommendation"];
  event: Schema["RecommendationsEvent"];
}) {
  const { detail, error } = useCatalogDetail(item.entity);
  const evidence = event.evidence.find(
    (e) =>
      e.entity.category === item.entity.category &&
      e.entity.id === item.entity.id,
  );
  const assessment =
    event.nutrition?.status === "success"
      ? event.nutrition.result.assessments.find(
          (a) =>
            a.entity.id === item.entity.id &&
            a.entity.category === item.entity.category,
        )
      : undefined;
  return (
    <article
      className={
        item.entity.category === "recipe"
          ? "recipe-card recommendation-card"
          : "restaurant-row recommendation-row"
      }
    >
      {detail?.images?.[0] && (
        <CatalogImage
          entity={item.entity}
          image={detail.images[0]}
          name={detail.data.name}
        />
      )}
      <div className="card-content">
        <h3>
          {detail?.data.name ||
            `${item.entity.category === "recipe" ? "Recipe" : "Restaurant"} ${item.entity.id}`}
        </h3>
        {!detail && <p className="note">{error || "Loading catalog facts…"}</p>}
        {detail && (
          <>
            <CatalogFacts category={item.entity.category} data={detail.data} />
          </>
        )}
        <h4 className="fit-heading">Why this fits</h4>
        <p>{item.explanation}</p>
        <p className="note">
          {assessment?.state === "supported"
            ? "Ingredient evidence supports the requested restrictions; cross-contact is not verified."
            : `Dietary evidence: ${assessment?.state ?? "unknown"}.`}
        </p>
        {[
          ...new Set([
            ...item.limitations,
            ...(evidence?.limitations ?? []),
            ...(assessment?.limitations ?? []),
          ]),
        ].map((limitation, i) => (
          <p className="note" key={i}>
            {limitation}
          </p>
        ))}
        {detail && item.entity.category === "recipe" && (
          <details>
            <summary>Ingredients</summary>
            <RecipeIngredients data={detail.data as Schema["RecipeData"]} />
          </details>
        )}
        <Sources
          citations={
            evidence?.citations.filter((c) =>
              item.citation_ids.includes(c.id),
            ) ?? []
          }
        />
        <Link
          className="card-link"
          href={`/catalog/${item.entity.category === "recipe" ? "recipes" : "restaurants"}/${encodeURIComponent(item.entity.id)}?returnTo=${encodeURIComponent(`/conversations/${event.conversation_id}`)}`}
        >
          View details for {detail?.data.name || item.entity.id}
        </Link>
      </div>
    </article>
  );
}
