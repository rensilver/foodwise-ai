"""Fixed public catalog resources; no caller-controlled filesystem access."""

from fastmcp import FastMCP

from food_recommender.application.catalog.resources import CatalogResources


def register_resources(server: FastMCP, store: CatalogResources) -> None:
    @server.resource("foodwise://culinary-map", mime_type="text/plain")
    async def culinary_map() -> str:
        """Imported culinary map paragraphs; synthetic course catalog."""
        return await store.read("culinary-map")

    @server.resource("foodwise://dataset-manifest", mime_type="application/json")
    async def dataset_manifest() -> str:
        """Public catalog source counts and content revisions."""
        return await store.read("dataset-manifest")

    @server.resource("foodwise://source-provenance", mime_type="application/json")
    async def source_provenance() -> str:
        """Public restaurant/recipe source hashes and ingestion attribution."""
        return await store.read("source-provenance")
