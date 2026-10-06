"use client";
import { useState } from "react";
import Link from "next/link";
import { Search, Sprout } from "lucide-react";
import { PRODUCT_NAME } from "../../lib/product";
import { Button } from "../ui/button";

export function SiteHeader() {
  const [category, setCategory] = useState("recipes");
  return (
    <header className="site-header">
      <div className="site-nav">
        <Link href="/" className="brand">
          <Sprout aria-hidden="true" />
          {PRODUCT_NAME}
        </Link>
        <form
          role="search"
          action={`/catalog/${category}`}
          className="catalog-search"
        >
          <label className="sr-only" htmlFor="search-category">
            Search category
          </label>
          <select
            id="search-category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="recipes">Recipes</option>
            <option value="restaurants">Restaurants</option>
          </select>
          <label className="sr-only" htmlFor="catalog-search">
            Search {category} by name
          </label>
          <input
            id="catalog-search"
            name="q"
            type="search"
            maxLength={200}
            placeholder={`Search ${category} by name…`}
          />
          <Button aria-label="Search catalog" variant="secondary">
            <Search size={20} aria-hidden="true" />
          </Button>
        </form>
      </div>
    </header>
  );
}
