"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import { formatDuration } from "../../lib/duration";
import { api, type Schema } from "../../lib/api/client";
export function useCatalogDetail(entity: Schema["EntityRef"]) {
  const [detail, setDetail] = useState<Schema["CatalogDetail"]>();
  const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController();
    const path =
      entity.category === "restaurant"
        ? "/api/v1/restaurants/{entity_id}"
        : "/api/v1/recipes/{entity_id}";
    void api(path, "get", {
      params: { entity_id: entity.id },
      signal: abort.signal,
    })
      .then((value) => {
        if (value.data.id !== entity.id)
          throw new Error("Catalog identity mismatch.");
        setDetail(value);
      })
      .catch((e) => {
        if (!abort.signal.aborted)
          setError(
            e instanceof Error ? e.message : "Catalog details unavailable.",
          );
      });
    return () => abort.abort();
  }, [entity.category, entity.id]);
  return { detail, error };
}
export function CatalogImage({
  entity,
  image,
  name,
}: {
  entity: Schema["EntityRef"];
  image: Schema["MediaReceipt"];
  name: string;
}) {
  const [failed, setFailed] = useState(false);
  const src = `/api/v1/${entity.category === "recipe" ? "recipes" : "restaurants"}/${encodeURIComponent(entity.id)}/images/${encodeURIComponent(image.id)}`;
  return (
    <figure className="catalog-image">
      {failed ? (
        <p className="image-placeholder note">
          Image unavailable. The linked catalog image could not be loaded.
        </p>
      ) : (
        <Image
          unoptimized
          className="result-image"
          src={src}
          loading="lazy"
          sizes="(min-width: 1120px) 33vw, (min-width: 600px) 50vw, 100vw"
          width={image.width}
          height={image.height}
          alt={`Catalog image associated with ${name}`}
          onError={() => setFailed(true)}
        />
      )}
      <figcaption className="note">
        Image from the linked catalog record.
      </figcaption>
    </figure>
  );
}
export function CatalogFacts({
  category,
  data,
  full = false,
}: {
  category: Schema["Category"];
  data: Schema["CatalogDetail"]["data"];
  full?: boolean;
}) {
  if (category === "restaurant") {
    const item = data as Schema["RestaurantData"];
    return (
      <>
        <dl className="facts">
          <dt>Cuisine</dt>
          <dd>{item.cuisine || "Unknown"}</dd>
          <dt>Location</dt>
          <dd>{item.location || "Unknown"}</dd>
          <dt>Source price band</dt>
          <dd>{item.price_band ? "$".repeat(item.price_band) : "Unknown"}</dd>
          {full && (
            <>
              <dt>Catalog rating</dt>
              <dd>
                {item.rating == null
                  ? "Unknown"
                  : `${item.rating} / 5 (dataset rating)`}
              </dd>
              <dt>Ambiance</dt>
              <dd>{item.vibe || "Unknown"}</dd>
              <dt>Environment</dt>
              <dd>{item.environment || "Unknown"}</dd>
            </>
          )}
        </dl>
        {full && (
          <>
            <p>{item.description}</p>
            <h3>Signature dishes</h3>
            <p>{item.signatures?.join(", ") || "Not provided"}</p>
            <h3>Dataset limitations</h3>
            <p>{item.shortcomings?.join(", ") || "Not provided"}</p>
            <p className="note">
              Hours, live menu availability and cross-contact safety are not
              verified.
            </p>
          </>
        )}
      </>
    );
  }
  const item = data as Schema["RecipeData"];
  return (
    <>
      <dl className="facts">
        <dt>Cuisine</dt>
        <dd>{item.cuisine || "Unknown"}</dd>
        <dt>Source time</dt>
        <dd>{formatDuration(item.total_time)}</dd>
        <dt>Servings</dt>
        <dd>{item.servings ?? "Unknown"}</dd>
      </dl>
      {full && (
        <>
          <dl className="facts">
            <dt>Preparation time</dt>
            <dd>{formatDuration(item.prep_time)}</dd>
            <dt>Cooking time</dt>
            <dd>{formatDuration(item.cook_time)}</dd>
          </dl>
          <h3>Ingredients</h3>
          {item.ingredients?.length ? (
            <ul>
              {item.ingredients.map((ingredient, i) => (
                <li key={i}>{ingredient}</li>
              ))}
            </ul>
          ) : (
            <p>Ingredients unknown.</p>
          )}
          <h3>Directions</h3>
          {item.directions?.length ? (
            <ol>
              {item.directions.map((direction, i) => (
                <li key={i}>{direction}</li>
              ))}
            </ol>
          ) : (
            <p>Directions not provided.</p>
          )}
          <p className="note">
            Verified nutrition, difficulty and cross-contact safety are unknown.
          </p>
        </>
      )}
    </>
  );
}
