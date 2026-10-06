"""Container-side restore checks; only the disposable P11-03 databases."""

import argparse
import asyncio
import hashlib
import json
import os
from uuid import UUID

import psycopg
from scripts.probe_phase11_persistence import dsn
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.domain.values import Category
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.search.image import PostgresImageSearch
from food_recommender.infrastructure.persistence.search.text import PostgresTextSearch
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork
from food_recommender.retrieval.embedding_contracts import CLIP_MODEL, CLIP_REVISION
from food_recommender.retrieval.models import TextPlan


def integrity() -> dict:
    with psycopg.connect(dsn()) as connection:
        constraints = connection.execute(
            "SELECT n.nspname, c.relname, k.conname, pg_get_constraintdef(k.oid), "
            "k.convalidated FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname IN ('public', 'foodwise_checkpoints') "
            "ORDER BY 1,2,3"
        ).fetchall()
        assert constraints and all(row[-1] for row in constraints)
        owners = connection.execute(
            "SELECT n.nspname, c.relname, c.relkind, pg_get_userbyid(c.relowner) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname IN ('public', 'foodwise_checkpoints') "
            "AND c.relkind IN ('r', 'S') ORDER BY 1,2"
        ).fetchall()
        assert owners and all(row[-1] == "foodwise" for row in owners)
        links = connection.execute(
            "SELECT m.id, r.record_type, r.record_id, r.recipe_id, "
            "v.restaurant_id FROM media m JOIN source_records r "
            "ON r.id=m.source_record_id LEFT JOIN reviews v ON v.id=r.review_id "
            "ORDER BY m.id"
        ).fetchall()
        assert len(links) == 118
        assert sum(row[1] == "recipe" and row[2] == row[3] for row in links) == 109
        assert sum(row[1] == "review" and row[4] is not None for row in links) == 9
        return {
            "constraints": len(constraints),
            "constraints_sha256": hashlib.sha256(
                json.dumps(constraints).encode()
            ).hexdigest(),
            "all_constraints_validated": True,
            "all_application_tables_and_sequences_owned_by_foodwise": True,
            "owners_sha256": hashlib.sha256(json.dumps(owners).encode()).hexdigest(),
            "recipe_image_links": 109,
            "review_restaurant_image_links": 9,
            "links_sha256": hashlib.sha256(json.dumps(links).encode()).hexdigest(),
        }


async def retrieval() -> dict:
    """Exercise real adapters with stored vectors; no re-embedding/provider calls."""
    engine = create_database_engine(os.environ["DATABASE_URL"])
    try:
        with psycopg.connect(dsn()) as connection:
            text = connection.execute(
                "SELECT e.embedding::text FROM text_embeddings e ORDER BY e.id LIMIT 1"
            ).fetchone()[0]
            images = connection.execute(
                "SELECT DISTINCT ON (s.record_type) e.embedding::text, "
                "COALESCE(s.recipe_id,v.restaurant_id), m.id, s.record_type, "
                "v.demo_profile_id FROM image_embeddings e "
                "JOIN media m ON m.id=e.media_id JOIN source_records s "
                "ON s.id=m.source_record_id LEFT JOIN reviews v ON v.id=s.review_id "
                "ORDER BY s.record_type, e.id"
            ).fetchall()
            assert {row[3] for row in images} == {"recipe", "review"}
        sessions = async_sessionmaker(engine)
        plan = TextPlan("pizza")
        text_search = PostgresTextSearch(sessions)
        result = {}
        for category in (Category.RESTAURANT, Category.RECIPE):
            for branch in ("lexical", "dense"):
                hits = await text_search.search(
                    plan, category, branch, tuple(json.loads(text))
                )
                assert hits and all(h.citation.entity == h.entity for h in hits)
                payload = [
                    (
                        h.entity.id,
                        h.citation.source_id,
                        h.citation.document_id,
                        h.lexical_score,
                        h.cosine_similarity,
                    )
                    for h in hits
                ]
                result[f"{category}-{branch}"] = {
                    "hits": len(hits),
                    "sha256": hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
                }
        for image in images:
            category = Category.RECIPE if image[3] == "recipe" else Category.RESTAURANT
            hits = await PostgresImageSearch(sessions).search(
                TextPlan(
                    "image",
                    entity_ids=(image[1],),
                    sources=(image[3],),
                    demo_profile_id=image[4],
                ),
                category,
                tuple(json.loads(image[0])),
                model=CLIP_MODEL,
                revision=CLIP_REVISION,
            )
            assert (
                hits and hits[0].entity.id == image[1] and hits[0].media_id == image[2]
            )
            assert abs(hits[0].cosine_similarity - 1) < 0.00001
            payload = [(h.entity.id, h.media_id, h.cosine_similarity) for h in hits]
            result[f"clip-{image[3]}-self-query"] = {
                "hits": len(hits),
                "sha256": hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
                "correct_entity_and_media": True,
            }
            if image[3] == "review":
                assert (
                    await PostgresImageSearch(sessions).search(
                        TextPlan(
                            "image",
                            sources=("review",),
                            demo_profile_id="other-profile",
                        ),
                        Category.RESTAURANT,
                        tuple(json.loads(image[0])),
                        model=CLIP_MODEL,
                        revision=CLIP_REVISION,
                    )
                    == ()
                )
                result[f"clip-{image[3]}-self-query"]["other_profile_excluded"] = True
        return result
    finally:
        await engine.dispose()


async def link_upload(conversation: UUID, media_id: str) -> dict:
    engine = create_database_engine(os.environ["DATABASE_URL"])
    try:
        with psycopg.connect(dsn()) as connection:
            owner = connection.execute(
                "SELECT session_id FROM conversations WHERE id=%s", (conversation,)
            ).fetchone()[0]
        async with PostgresUnitOfWork(async_sessionmaker(engine)) as uow:
            await uow.conversations.link_media(owner, conversation, media_id)
            await uow.commit()
        return {"upload_linked": True}
    finally:
        await engine.dispose()


def deleted(conversation: UUID) -> dict:
    with psycopg.connect(dsn()) as connection:
        for table, field in (
            ("conversations", "id"),
            ("profiles", "conversation_id"),
            ("messages", "conversation_id"),
            ("conversation_media", "conversation_id"),
        ):
            assert (
                connection.execute(
                    f"SELECT count(*) FROM {table} WHERE {field}=%s", (conversation,)
                ).fetchone()[0]
                == 0
            )
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            assert (
                connection.execute(
                    f"SELECT count(*) FROM foodwise_checkpoints.{table} WHERE thread_id=%s",
                    (str(conversation),),
                ).fetchone()[0]
                == 0
            )
        assert (
            connection.execute(
                "SELECT count(*) FROM media WHERE owner_session_id IS NOT NULL"
            ).fetchone()[0]
            == 0
        )
    return {"context_and_checkpoint_rows_removed": True, "owned_upload_removed": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=("integrity", "retrieval", "link-upload", "deleted")
    )
    parser.add_argument("--conversation", type=UUID)
    parser.add_argument("--media-id")
    args = parser.parse_args()
    if args.operation == "integrity":
        result = integrity()
    elif args.operation == "retrieval":
        result = asyncio.run(retrieval())
    else:
        if args.conversation is None:
            parser.error("--conversation required")
        if args.operation == "link-upload":
            if args.media_id is None:
                parser.error("--media-id required")
            result = asyncio.run(link_upload(args.conversation, args.media_id))
        else:
            result = deleted(args.conversation)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
