"""Model identity and vector validation shared by retrieval and its adapters."""

from food_recommender.domain.catalog import EmbeddingData

CLIP_MODEL = "openai/clip-vit-base-patch32"
CLIP_REVISION = "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
MINILM_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MINILM_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def validate_clip(values: tuple[float, ...], model: str, revision: str) -> None:
    if (model, revision) != (CLIP_MODEL, CLIP_REVISION):
        raise ValueError("Incompatible CLIP model/revision")
    EmbeddingData(
        id="query",
        parent_id="query",
        model=model,
        revision=revision,
        input_hash="0" * 64,
        values=values,
    )


def validate_query(values: tuple[float, ...], model: str, revision: str) -> None:
    if (model, revision) != (MINILM_MODEL, MINILM_REVISION):
        raise ValueError("Incompatible text embedding model/revision")
    EmbeddingData(
        id="query",
        parent_id="query",
        model=model,
        revision=revision,
        input_hash="0" * 64,
        values=values,
    )
