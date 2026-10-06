"use client";
import { PageShell } from "../../components/layout/page-shell";
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
    /^(?:\/|\/(?:catalog\/(?:restaurants|recipes)(?:\?[^#]*)?|conversations\/[A-Za-z0-9-]+))$/.test(
      returnTo,
    ) &&
    !returnTo.includes("\\")
      ? returnTo
      : fallback;
  return (
    <PageShell
      className="detail-page"
      sidebar={
        <>
          <h2 className="sidebar-title">From the catalog</h2>
          <p className="note">
            Inspect the ingredients, directions and original sources before
            choosing.
          </p>
          <Link href={destination}>Back to browsing</Link>
        </>
      }
      active={entity.category === "recipe" ? "recipes" : "restaurants"}
    >
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
          <div
            className={
              detail.images?.length ? "detail-layout" : "detail-reading"
            }
          >
            <div className="detail-images">
              {detail.images?.map((image) => (
                <CatalogImage
                  key={image.id}
                  entity={entity}
                  image={image}
                  name={detail.data.name}
                />
              ))}
            </div>
            <div className="detail-facts">
              <h2>
                {entity.category === "recipe"
                  ? "Recipe details"
                  : "Restaurant details"}
              </h2>
              <CatalogFacts
                category={entity.category}
                data={detail.data}
                full
              />
            </div>
          </div>
          <Sources citations={detail.citations} />
          <p className="note">
            Source record: {detail.data.source_record_id}. Version{" "}
            {detail.version}.
          </p>
        </>
      )}
    </PageShell>
  );
}
