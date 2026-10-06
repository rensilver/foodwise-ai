"use client";
import Link from "next/link";
import { CatalogCard, CatalogSkeletons } from "./catalog-card";
import { useCatalogPage } from "./use-catalog-page";
export function RecipeDiscovery() {
  const { page, error } = useCatalogPage("recipe", "limit=6");
  return (
    <section className="discovery" aria-labelledby="discovery-title">
      <div className="section-heading">
        <h2 id="discovery-title">Explore recipes</h2>
        <Link href="/catalog/recipes">Browse all recipes</Link>
      </div>
      <p className="note">
        From the teaching catalog. Preferences aren’t applied to browsing; use a
        meal request for personalized suggestions.
      </p>
      {!page && !error && (
        <>
          <p role="status">Loading recipe preview…</p>
          <CatalogSkeletons />
        </>
      )}
      {error && (
        <p className="notice" role="status">
          Recipe preview unavailable. You can still send a meal request or
          browse the catalog.
        </p>
      )}
      {page &&
        (page.items.length ? (
          <div className="recipe-grid">
            {page.items.map((detail) => (
              <CatalogCard
                key={detail.data.id}
                category="recipe"
                detail={detail}
                returnTo="/"
              />
            ))}
          </div>
        ) : (
          <p className="notice">
            No recipes in the catalog yet. You can still ask for a place to eat.
          </p>
        ))}
      <div className="restaurant-invitation">
        <h3>Prefer eating out?</h3>
        <p>Explore places by cuisine, location and source price band.</p>
        <Link href="/catalog/restaurants">Browse restaurants</Link>
      </div>
    </section>
  );
}
