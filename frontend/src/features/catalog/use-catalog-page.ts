"use client";
import { useEffect, useState } from "react";
import { api, type Schema } from "../../lib/api/client";
export function useCatalogPage(category: Schema["Category"], query: string) {
  const key = `${category}:${query}`;
  const [result, setResult] = useState<{
    key: string;
    page?: Schema["CatalogPage"];
    error?: string;
  }>();
  useEffect(() => {
    const abort = new AbortController();
    const params = new URLSearchParams(query);
    if (!params.has("limit")) params.set("limit", "12");
    void api(
      category === "recipe" ? "/api/v1/recipes" : "/api/v1/restaurants",
      "get",
      { query: params, signal: abort.signal },
    )
      .then((page) => {
        if (!abort.signal.aborted) setResult({ key, page });
      })
      .catch((error) => {
        if (!abort.signal.aborted)
          setResult({
            key,
            error:
              error instanceof Error ? error.message : "Catalog unavailable.",
          });
      });
    return () => abort.abort();
  }, [category, query, key]);
  return result?.key === key ? result : { page: undefined, error: undefined };
}
