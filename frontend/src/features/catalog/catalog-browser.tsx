"use client";
import { PageShell } from "../../components/layout/page-shell";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type Schema } from "../../lib/api/client";
import { Button } from "../../components/ui/button";
import { CatalogCard, CatalogSkeletons } from "./catalog-card";
import { useCatalogPage } from "./use-catalog-page";
export function CatalogBrowser({
  category,
  query,
}: {
  category: Schema["Category"];
  query: string;
}) {
  const router = useRouter();
  const { page, error } = useCatalogPage(category, query);
  const section = category === "recipe" ? "recipes" : "restaurants";
  const filters = new URLSearchParams(query);
  const [cuisine, setCuisine] = useState(filters.get("cuisine") ?? "");
  function pageLink(offset: number) {
    const next = new URLSearchParams(query);
    next.set("offset", String(offset));
    return `/catalog/${section}?${next}`;
  }
  return (
    <PageShell
      active={category === "recipe" ? "recipes" : "restaurants"}
      sidebarLabel="Menu and filters"
      sidebar={
        <>
          <h2 className="sidebar-title">Filter {section}</h2>{" "}
          <form
            key={query}
            className="stack catalog-filters"
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              const next = new URLSearchParams();
              for (const [key, value] of form)
                if (String(value).trim()) next.set(key, String(value).trim());
              router.push(`/catalog/${section}?${next}`);
            }}
          >
            <label>
              Search by name
              <input
                name="q"
                maxLength={200}
                defaultValue={filters.get("q") ?? ""}
              />
            </label>
            <label>
              Cuisine
              <input
                name="cuisine"
                maxLength={100}
                value={cuisine}
                onChange={(e) => setCuisine(e.target.value)}
              />
            </label>
            {category === "restaurant" && (
              <>
                <label>
                  Location
                  <input
                    name="location"
                    maxLength={100}
                    defaultValue={filters.get("location") ?? ""}
                  />
                </label>
                <label>
                  Maximum source price band
                  <select
                    name="price_band"
                    defaultValue={filters.get("price_band") ?? ""}
                  >
                    <option value="">Any</option>
                    {[1, 2, 3, 4].map((n) => (
                      <option key={n} value={n}>
                        {"$".repeat(n)}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            )}
            <div
              className="cuisine-shortcuts"
              role="group"
              aria-label="Cuisine shortcuts"
            >
              {["Italian", "American", "Indian", "Thai"].map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={cuisine === value}
                  onClick={() => setCuisine(cuisine === value ? "" : value)}
                >
                  {value}
                </button>
              ))}
            </div>
            <Button type="submit">Apply filters</Button>
            <Link href={`/catalog/${section}`}>Reset filters</Link>
          </form>
          <p className="note">
            Catalog filters do not apply your conversation preferences.
          </p>
        </>
      }
    >
      <h1>{category === "recipe" ? "Recipes to cook" : "Places to eat"}</h1>
      <p className="note">
        Synthetic teaching catalog, with local administrator entries. Ratings
        and reviews are dataset observations; live availability and verified
        nutrition are unknown.
      </p>
      {error && (
        <p className="notice error" role="alert">
          {error} <Link href={`/catalog/${section}`}>Reset filters</Link>
        </p>
      )}
      {!page && !error && (
        <>
          <p role="status">Loading catalog…</p>
          <CatalogSkeletons />
        </>
      )}
      {page && (
        <>
          <p role="status">
            {page.total} entries
            {page.total > 0 &&
              `; showing ${page.offset + 1}–${page.offset + page.items.length}`}
            .
          </p>
          {!page.items.length && (
            <p className="notice">
              No entries match these filters. Edit the search or reset filters.
            </p>
          )}
          <div
            className={
              category === "recipe" ? "recipe-grid" : "restaurant-list"
            }
          >
            {page.items.map((detail) => (
              <CatalogCard
                key={detail.data.id}
                detail={detail}
                category={category}
                returnTo={`/catalog/${section}${query ? `?${query}` : ""}`}
              />
            ))}
          </div>
          <nav aria-label="Catalog pages" className="actions">
            {page.offset > 0 && (
              <Link href={pageLink(Math.max(0, page.offset - page.limit))}>
                Previous page
              </Link>
            )}
            {page.offset + page.limit < page.total && (
              <Link href={pageLink(page.offset + page.limit)}>Next page</Link>
            )}
          </nav>
        </>
      )}
    </PageShell>
  );
}
