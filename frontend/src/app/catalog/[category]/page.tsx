import { notFound } from "next/navigation";
import { CatalogBrowser } from "../../../features/catalog/catalog-browser";
export default async function Browse({
  params,
  searchParams,
}: {
  params: Promise<{ category: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { category } = await params;
  if (!["restaurants", "recipes"].includes(category)) notFound();
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(await searchParams))
    if (typeof value === "string") query.set(key, value);
  return (
    <CatalogBrowser
      key={`${category}:${query}`}
      category={category === "recipes" ? "recipe" : "restaurant"}
      query={query.toString()}
    />
  );
}
