import Link from "next/link";
import { CookingPot } from "lucide-react";
import type { Schema } from "../../lib/api/client";
import {
  CatalogFacts,
  CatalogImage,
} from "../recommendations/catalog-presentation";
export function CatalogCard({
  detail,
  category,
  returnTo,
}: {
  detail: Schema["CatalogDetail"];
  category: Schema["Category"];
  returnTo: string;
}) {
  const recipe = category === "recipe";
  return (
    <article className={recipe ? "recipe-card" : "restaurant-row"}>
      {detail.images?.[0] ? (
        <CatalogImage
          entity={{ category, id: detail.data.id }}
          image={detail.images[0]}
          name={detail.data.name}
        />
      ) : (
        recipe && (
          <div className="image-placeholder">
            <CookingPot size={32} aria-hidden="true" />
            <span>No catalog image</span>
          </div>
        )
      )}
      <div className="card-content">
        <h2>{detail.data.name}</h2>
        <CatalogFacts category={category} data={detail.data} />
        <Link
          className="card-link"
          href={`/catalog/${recipe ? "recipes" : "restaurants"}/${encodeURIComponent(detail.data.id)}?returnTo=${encodeURIComponent(returnTo)}`}
          aria-label={`View details for ${detail.data.name}`}
        >
          View {recipe ? "recipe" : "restaurant"}
        </Link>
      </div>
    </article>
  );
}
export function CatalogSkeletons() {
  return (
    <div className="recipe-grid" aria-hidden="true">
      {[0, 1, 2].map((n) => (
        <div key={n} className="catalog-skeleton">
          <div />
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}
