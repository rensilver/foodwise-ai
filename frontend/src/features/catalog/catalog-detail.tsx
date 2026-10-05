"use client";
import Link from "next/link";
import type { Schema } from "../../lib/api/client";
import {
  CatalogFacts,
  CatalogImage,
  useCatalogDetail,
} from "../recommendations/catalog-presentation";
import { Sources } from "../recommendations/sources";
export function CatalogDetail({
  entity,
  returnTo,
}: {
  entity: Schema["EntityRef"];
  returnTo?: string;
}) {
  const { detail, error } = useCatalogDetail(entity);
  const fallback = `/catalog/${entity.category === "recipe" ? "recipes" : "restaurants"}`;
  const destination =
    returnTo &&
    /^\/(?:catalog\/(?:restaurants|recipes)(?:\?[^#]*)?|conversations\/[A-Za-z0-9-]+)$/.test(
      returnTo,
    ) &&
    !returnTo.includes("\\")
      ? returnTo
      : fallback;
  return (
    <main id="main" className="workspace">
      <Link href={destination}>Return to results</Link>
      <h1>{detail?.data.name || "Catalog details"}</h1>
      <p className="note">
        {detail?.data.source_id === "local-admin"
          ? "Local administrator entry"
          : "Synthetic teaching catalog"}
      </p>
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      {!detail && !error && <p role="status">Loading source-backed details…</p>}
      {detail && (
        <>
          {detail.images?.map((image) => (
            <CatalogImage
              key={image.id}
              entity={entity}
              image={image}
              name={detail.data.name}
            />
          ))}
          <CatalogFacts category={entity.category} data={detail.data} full />
          <Sources citations={detail.citations} />
          <p className="note">
            Source record: {detail.data.source_record_id}. Version{" "}
            {detail.version}.
          </p>
        </>
      )}
    </main>
  );
}
