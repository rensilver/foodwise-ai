"""Explicit CPU/pgvector comparison on frozen source-backed multimodal labels."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import resource
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.composition import build_multimodal_retrieval
from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import Category, ConstraintKind, Origin, Strength
from food_recommender.infrastructure.embeddings.clip import CLIPEncoder
from food_recommender.infrastructure.embeddings.minilm import MiniLMEncoder
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.models.catalog import (
    Recipe,
    Restaurant,
    Review,
)
from food_recommender.infrastructure.persistence.models.embeddings import (
    ImageEmbedding,
    TextEmbedding,
)
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    Media,
    Source,
    SourceRecord,
)
from food_recommender.retrieval.late_fusion import FusionWeights
from food_recommender.retrieval.metrics import ndcg, recall
from food_recommender.retrieval.models import TextPlan

SETTINGS = {
    "text_only": (1, 0),
    "balanced": (0.5, 0.5),
    "text_heavy": (0.8, 0.2),
    "image_heavy": (0.2, 0.8),
    "initial_default": (0.6, 0.4),
}


def latency(values):
    return {
        "median": median(values),
        "p95": sorted(values)[int(0.95 * (len(values) - 1))],
        "max": max(values),
    }


async def evaluate(args):
    repository = Path(__file__).resolve().parents[2]
    labels = json.loads(args.queries.read_text())
    for filename, expected in labels["source_hashes"].items():
        assert (
            hashlib.sha256((repository / filename).read_bytes()).hexdigest() == expected
        ), "Source label revision changed"
    manifest_file = repository / "evaluation/phase0/recipe_media_manifest.json"
    assert (
        hashlib.sha256(manifest_file.read_bytes()).hexdigest()
        == labels["media_manifest_sha256"]
    )
    expected_images = {
        str(r["recipe_id"]): r["sha256"]
        for r in json.loads(manifest_file.read_text())["rows"]
    }
    started = perf_counter()
    minilm = await asyncio.to_thread(MiniLMEncoder, args.minilm_root)
    clip = await asyncio.to_thread(CLIPEncoder, args.clip_root)
    load_ms = (perf_counter() - started) * 1000
    engine = create_database_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = build_multimodal_retrieval(
        sessions,
        minilm,
        clip,
        Path(os.environ["MEDIA_ROOT"]),
        allow_catalog_queries=True,
    )
    violations = {
        name: 0
        for name in (
            "fabricated_entities",
            "fabricated_citations",
            "hard_constraint_violations",
            "metadata_filter_violations",
            "review_scope_violations",
            "image_association_violations",
            "duplicate_entities",
        )
    }
    try:
        async with sessions() as session:
            tables = [
                ("restaurants", Restaurant),
                ("recipes", Recipe),
                ("reviews", Review),
                ("documents", Document),
                ("media", Media),
                ("text_embeddings", TextEmbedding),
                ("image_embeddings", ImageEmbedding),
            ]
            corpus = {
                name: await session.scalar(select(func.count()).select_from(model))
                for name, model in tables
            }
            restaurants = {
                r.id: r for r in (await session.scalars(select(Restaurant))).all()
            }
            recipes = {r.id: r for r in (await session.scalars(select(Recipe))).all()}
            reviews = {r.id: r for r in (await session.scalars(select(Review))).all()}
            docs = {r.id: r for r in (await session.scalars(select(Document))).all()}
            records = {
                r.id: r for r in (await session.scalars(select(SourceRecord))).all()
            }
            sources = {r.id: r for r in (await session.scalars(select(Source))).all()}
            media = {r.id: r for r in (await session.scalars(select(Media))).all()}
            db_versions = {
                "postgres": await session.scalar(text("SHOW server_version")),
                "pgvector_extension": await session.scalar(
                    text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                ),
            }

        def actual(record):
            if record.recipe_id:
                return ("recipe", record.recipe_id)
            if record.review_id:
                return ("restaurant", reviews[record.review_id].restaurant_id)
            return ("restaurant", record.restaurant_id)

        recipe_media = {}
        review_images = 0
        for m in media.values():
            record = records[m.source_record_id]
            if record.recipe_id:
                match = re.search(r"#recipe(\d+)\.png$", m.original_locator or "")
                assert match and match[1] == record.recipe_id, (
                    "Recipe image identity mismatch"
                )
                assert m.input_hash == expected_images[record.recipe_id], (
                    "Original image hash differs from validated manifest"
                )
                assert record.recipe_id not in recipe_media, (
                    "Unexpected multiple recipe images"
                )
                recipe_media[record.recipe_id] = m
            elif record.review_id:
                assert record.review_id in reviews
                review_images += 1
        assert set(recipe_media) == set(expected_images), (
            "Incomplete real recipe media corpus"
        )

        def validate(outcome, plan):
            seen = set()
            for c in outcome.candidates:
                ref = c.evidence.entity
                key = (ref.category.value, ref.id)
                violations["duplicate_entities"] += key in seen
                seen.add(key)
                entities = recipes if ref.category == Category.RECIPE else restaurants
                item = entities.get(ref.id)
                if item is None:
                    violations["fabricated_entities"] += 1
                    continue

                def normalize(value):
                    return " ".join(value.casefold().split())

                if (
                    plan.entity_ids
                    and ref.id not in plan.entity_ids
                    or plan.cuisine
                    and item.normalized_cuisine != normalize(plan.cuisine)
                ):
                    violations["metadata_filter_violations"] += 1
                if ref.category == Category.RESTAURANT:
                    if (
                        plan.location
                        and item.normalized_location != normalize(plan.location)
                        or plan.max_price_band is not None
                        and (
                            item.price_band is None
                            or item.price_band > plan.max_price_band
                        )
                    ):
                        violations["metadata_filter_violations"] += 1
                if any(
                    a.constraint.strength == Strength.HARD
                    and a.state.value != "supported"
                    for a in c.assessments
                ) or len(c.assessments) != len(plan.constraints):
                    violations["hard_constraint_violations"] += 1
                for citation in c.evidence.citations:
                    doc = docs.get(citation.document_id)
                    record = records.get(doc.source_record_id) if doc else None
                    source = sources.get(record.source_id) if record else None
                    if (
                        doc is None
                        or record is None
                        or source is None
                        or citation.excerpt != doc.text
                        or citation.source_id != source.id
                        or citation.record_id != record.record_id
                        or actual(record) != key
                        or citation.entity != ref
                    ):
                        violations["fabricated_citations"] += 1
                        continue
                    if record.record_type not in plan.sources:
                        violations["fabricated_citations"] += 1
                    if (
                        record.review_id
                        and reviews[record.review_id].demo_profile_id
                        != plan.demo_profile_id
                    ):
                        violations["review_scope_violations"] += 1
                for media_id in c.media_ids:
                    m = media.get(media_id)
                    if m is None or actual(records[m.source_record_id]) != key:
                        violations["image_association_violations"] += 1

        rows, summaries = [], {}
        for name, configured in SETTINGS.items():
            metrics, times = defaultdict(list), []
            for q in labels["queries"]:
                plan = TextPlan(
                    q["query"],
                    categories=tuple(Category(c) for c in q["categories"]),
                    sources=tuple(q["sources"]),
                    constraints=tuple(
                        Constraint(
                            ConstraintKind.ALLERGEN, a, Strength.HARD, Origin.EXPLICIT
                        )
                        for a in q.get("hard_allergens", [])
                    ),
                    **{
                        k: tuple(v) if k == "entity_ids" else v
                        for k, v in q["filters"].items()
                    },
                )
                m = (
                    recipe_media[q["image_recipe_id"]]
                    if "image_recipe_id" in q and configured[1]
                    else None
                )
                outcomes = [
                    await service.run(
                        plan,
                        weights=FusionWeights(*configured),
                        media_id=m.id if m else None,
                        session_id=UUID(int=0) if m else None,
                    )
                    for _ in range(2)
                ]
                first, result = outcomes
                assert result.status == first.status == q["expected_status"], (
                    f"Unexpected status for {name}/{q['id']}"
                )
                assert [
                    (c.evidence.entity, c.evidence.relevance) for c in first.candidates
                ] == [
                    (c.evidence.entity, c.evidence.relevance) for c in result.candidates
                ], "Unstable fusion"
                validate(result, plan)
                times.append(result.elapsed_ms)
                entry = {
                    "id": q["id"],
                    "setting": name,
                    "query_modality": "image"
                    if m
                    else "CLIP text"
                    if configured[1]
                    else "text only",
                    "status": result.status,
                    "first_query_ms": first.elapsed_ms,
                    "warm_query_ms": result.elapsed_ms,
                    "limitations": result.limitations,
                    "categories": {},
                }
                for category in result.categories:
                    candidates = category.fusion.candidates
                    ranked = tuple(c.evidence.entity.id for c in candidates)
                    positive = set(q["relevant"][category.category.value])
                    r, n = recall(ranked, positive, 20), ndcg(ranked, positive, 5)
                    if r is not None:
                        metrics["recall_at_20"].append(r)
                        metrics["ndcg_at_5"].append(n)
                    entities = (
                        recipes if category.category == Category.RECIPE else restaurants
                    )
                    cuisines = [
                        entities[identity].normalized_cuisine for identity in ranked[:5]
                    ]
                    diversity = (
                        len({c for c in cuisines if c}) / len(cuisines)
                        if cuisines
                        else None
                    )
                    if diversity is not None:
                        metrics["cuisine_diversity_at_5"].append(diversity)
                    entry["categories"][category.category.value] = {
                        "ranked_ids": ranked,
                        "recall_at_20": r,
                        "ndcg_at_5": n,
                        "cuisine_diversity_at_5": diversity,
                        "effective_weights": {
                            "text": category.fusion.text_weight,
                            "image": category.fusion.image_weight,
                        },
                        "top5_components": [
                            {
                                "id": c.evidence.entity.id,
                                "relevance": c.evidence.relevance,
                                "text_score": c.evidence.text_score,
                                "image_score": c.evidence.image_score,
                                "rrf_score": c.rrf_score,
                                "text_cosine_similarity": c.text_cosine_similarity,
                                "image_cosine_similarity": c.image_cosine_similarity,
                                "media_ids": c.media_ids,
                                "document_ids": [
                                    cit.document_id for cit in c.evidence.citations
                                ],
                            }
                            for c in candidates[:5]
                        ],
                    }
                rows.append(entry)
            summaries[name] = {
                "configured_weights": {"text": configured[0], "image": configured[1]},
                **{metric: mean(values) for metric, values in metrics.items()},
                "warm_latency_ms": latency(times),
            }
            print(json.dumps({"setting": name, **summaries[name]}), flush=True)
        checks = []
        for identity in ("1", "7", "25"):
            m = recipe_media[identity]
            result = await service.run(
                TextPlan(
                    "image query", categories=(Category.RECIPE,), sources=("recipe",)
                ),
                media_id=m.id,
                session_id=UUID(int=0),
                use_text=False,
            )
            assert (
                result.status == "success"
                and result.candidates[0].evidence.entity.id == identity
            )
            validate(
                result,
                TextPlan(
                    "image query", categories=(Category.RECIPE,), sources=("recipe",)
                ),
            )
            checks.append(
                {
                    "query_recipe_id": identity,
                    "top1_recipe_id": result.candidates[0].evidence.entity.id,
                    "elapsed_ms": result.elapsed_ms,
                }
            )
        text_image_checks = []
        for identity, query in (
            ("1", "a photo of margherita pizza"),
            ("7", "a bowl of tomato soup"),
            ("25", "a bowl of Japanese ramen"),
        ):
            hits = await service.images.text(
                TextPlan(query, categories=(Category.RECIPE,), sources=("recipe",))
            )
            expected_rank = next(
                (i for i, h in enumerate(hits, 1) if h.entity.id == identity), None
            )
            text_image_checks.append(
                {
                    "query": query,
                    "expected_recipe_id": identity,
                    "expected_rank": expected_rank,
                    "top1_recipe_id": hits[0].entity.id if hits else None,
                }
            )
        assert not any(violations.values()), "Grounding/constraint violation"
        report = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "labels_version": labels["version"],
            "labels_sha256": hashlib.sha256(args.queries.read_bytes()).hexdigest(),
            "label_scope": labels["label_scope"],
            "source_hashes": labels["source_hashes"],
            "media_manifest_sha256": labels["media_manifest_sha256"],
            "models": {
                "text": {
                    "model": minilm.model_id,
                    "revision": minilm.revision,
                    "dimension": 384,
                },
                "image": {
                    "model": clip.model_id,
                    "revision": clip.revision,
                    "dimension": 512,
                    "file_hashes": json.loads(
                        (args.clip_root / "foodwise-model.json").read_text()
                    )["files"],
                },
            },
            "device": "cpu",
            "corpus": corpus,
            "association_checks": {
                "recipe_images": len(recipe_media),
                "linked_review_images": review_images,
            },
            "versions": {
                **db_versions,
                **{
                    p: importlib.metadata.version(p)
                    for p in (
                        "transformers",
                        "sentence-transformers",
                        "torch",
                        "sqlalchemy",
                        "pgvector",
                    )
                },
            },
            "hardware": {
                "platform": platform.platform(),
                "logical_cpus": os.cpu_count(),
                "cpu": next(
                    (
                        line.split(":", 1)[1].strip()
                        for line in Path("/proc/cpuinfo").read_text().splitlines()
                        if line.startswith("model name")
                    ),
                    "unknown",
                ),
                "memory_kib": next(
                    line
                    for line in Path("/proc/meminfo").read_text().splitlines()
                    if line.startswith("MemTotal")
                ),
                "process_peak_rss_mib": resource.getrusage(
                    resource.RUSAGE_SELF
                ).ru_maxrss
                / 1024,
            },
            "model_load_ms": load_ms,
            "fusion": {
                "text_branch": "RRF k=60 equal weights",
                "normalization": "min-max per category/modality; equal nonempty = 1",
                "aggregation": "maximum per canonical entity/modality; stable ID ties",
                "missing_modality": "renormalize active weights and report limitations",
            },
            "summaries": summaries,
            "violations": violations,
            "image_only_checks": checks,
            "clip_text_to_image_checks": text_image_checks,
            "usage": {"openai_calls": 0, "trend_searches": 0, "provider_tokens": 0},
            "queries": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "queries": len(labels["queries"]),
                    "settings": len(SETTINGS),
                    "violations": violations,
                }
            )
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minilm-root", type=Path, required=True)
    parser.add_argument("--clip-root", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(evaluate(parser.parse_args()))
