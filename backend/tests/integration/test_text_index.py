import re

import pytest
from sqlalchemy import func, select
from test_ingestion_store import seed_store as seed_store

from food_recommender.infrastructure.embeddings import TextEmbedding
from food_recommender.infrastructure.text_encoder import MINILM_MODEL, MINILM_REVISION
from food_recommender.infrastructure.text_index import TextIndexer
from food_recommender.ingestion.adapters import adapt_recipe
from food_recommender.ingestion.models import SeedItem
from food_recommender.ingestion.seed import artifact, source_record


class Encoder:
    model_id = MINILM_MODEL
    revision = MINILM_REVISION
    max_tokens = 254
    calls = 0

    def offsets(self, text):
        return tuple((m.start(), m.end()) for m in re.finditer(r"\S+", text))

    def encode(self, texts):
        self.calls += 1
        return tuple((1.0,) + (0.0,) * 383 for _ in texts)


@pytest.mark.asyncio
async def test_index_batches_are_hash_idempotent_and_preserve_canonical_ingredients(
    seed_store, tmp_path
):
    store, connection = seed_store
    raw = {
        "id": 1,
        "name": "Soup",
        "ingredients": ["rice"] * 600 + ["peanut"],
        "directions": ["boil"],
    }
    path = tmp_path / "Recipes.json"
    path.write_text("source")
    source = artifact(path, "course-recipes").source
    record = source_record(source, "recipe", "1", raw=raw)
    await store.upsert(
        SeedItem(adapt_recipe(raw, path.name).data, (source,), (record,), inputs=(raw,))
    )
    encoder = Encoder()
    index = TextIndexer(store.sessions, encoder)
    first = await index.build(batch_size=2)
    assert first == {"documents": 3, "embedded": 3, "unchanged": 0}
    assert encoder.calls == 2
    assert await index.build() == {"documents": 3, "embedded": 0, "unchanged": 3}
    assert encoder.calls == 2
    assert (
        await connection.execute(select(func.count()).select_from(TextEmbedding))
    ).scalar_one() == 3


@pytest.mark.asyncio
async def test_caption_chunk_preserves_imported_attribution_and_media_reference(
    seed_store, tmp_path
):
    from food_recommender.infrastructure.provenance import Document
    from food_recommender.ingestion.adapters import adapt_recipe
    from food_recommender.ingestion.seed import caption_document

    store, connection = seed_store
    raw = {"id": 1, "name": "Soup"}
    path = tmp_path / "Recipes.json"
    path.write_text("source")
    source = artifact(path, "course-recipes").source
    record = source_record(source, "recipe", "1", raw=raw)
    caption = caption_document(record, "Looks like soup")
    await store.upsert(
        SeedItem(
            adapt_recipe(raw, path.name).data,
            (source,),
            (record,),
            (caption,),
            inputs=(raw,),
        )
    )
    await TextIndexer(store.sessions, Encoder()).build()
    rows = (
        (
            await connection.execute(
                select(Document.__table__).where(
                    Document.kind.like("retrieval_caption:%")
                )
            )
        )
        .mappings()
        .all()
    )
    assert len(rows) == 1
    assert rows[0]["attribution"] == "imported"
    assert rows[0]["text"] == caption.text
