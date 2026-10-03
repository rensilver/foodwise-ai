"""Measure the initial text-only baseline on an explicitly selected seeded DB."""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import Category, ConstraintKind, Origin, Strength
from food_recommender.infrastructure.catalog import Recipe, Restaurant, Review
from food_recommender.infrastructure.embeddings import TextEmbedding
from food_recommender.infrastructure.persistence import create_database_engine
from food_recommender.infrastructure.provenance import Document, Source, SourceRecord
from food_recommender.infrastructure.text_encoder import MiniLMEncoder
from food_recommender.infrastructure.text_search import PostgresTextSearch
from food_recommender.retrieval.metrics import ndcg, recall
from food_recommender.retrieval.models import TextPlan
from food_recommender.retrieval.service import TextRetrieval


async def evaluate(args):
    root = Path(__file__).resolve().parents[2]
    labels = json.loads(args.queries.read_text())
    for filename, expected in labels["source_hashes"].items():
        assert hashlib.sha256((root / filename).read_bytes()).hexdigest() == expected, (
            "Source label revision changed"
        )
    started = perf_counter()
    encoder = await asyncio.to_thread(MiniLMEncoder, args.model_root)
    model_load_ms = (perf_counter() - started) * 1000
    engine = create_database_engine(os.environ["DATABASE_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = TextRetrieval(PostgresTextSearch(sessions), encoder)
    rows = []
    latencies = []
    metrics = defaultdict(list)
    violations = {
        "fabricated_entities": 0,
        "fabricated_citations": 0,
        "hard_constraint_violations": 0,
        "review_scope_violations": 0,
        "duplicate_entities": 0,
    }
    try:
        async with sessions() as session:
            corpus = {
                name: (await session.scalar(select(func.count()).select_from(model)))
                for name, model in [
                    ("restaurants", Restaurant),
                    ("recipes", Recipe),
                    ("reviews", Review),
                    ("documents", Document),
                    ("text_embeddings", TextEmbedding),
                ]
            }
            db_versions = {
                "postgres": await session.scalar(text("SHOW server_version")),
                "pgvector_extension": await session.scalar(
                    text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                ),
            }
            cuisines = {
                Category.RESTAURANT: dict(
                    (
                        await session.execute(
                            select(Restaurant.id, Restaurant.normalized_cuisine)
                        )
                    ).all()
                ),
                Category.RECIPE: dict(
                    (
                        await session.execute(
                            select(Recipe.id, Recipe.normalized_cuisine)
                        )
                    ).all()
                ),
            }
        for query in labels["queries"]:
            plan = TextPlan(
                query["query"],
                categories=tuple(Category(c) for c in query["categories"]),
                sources=tuple(query["sources"]),
                constraints=tuple(
                    Constraint(
                        ConstraintKind.ALLERGEN, a, Strength.HARD, Origin.EXPLICIT
                    )
                    for a in query.get("hard_allergens", [])
                ),
                **{
                    key: tuple(value) if key == "entity_ids" else value
                    for key, value in query["filters"].items()
                },
            )
            outcomes = [await service.run(plan) for _ in range(2)]
            assert all(o.status == query["expected_status"] for o in outcomes), (
                f"Unexpected outcome for {query['id']}"
            )
            first, second = outcomes
            assert [(c.evidence.entity, c.rrf_score) for c in first.candidates] == [
                (c.evidence.entity, c.rrf_score) for c in second.candidates
            ], "Unstable rankings"
            latencies.append(second.elapsed_ms)
            entry = {
                "id": query["id"],
                "status": second.status,
                "first_query_ms": first.elapsed_ms,
                "warm_query_ms": second.elapsed_ms,
                "categories": {},
            }
            for category in plan.categories:
                candidates = tuple(
                    c
                    for c in second.candidates
                    if c.evidence.entity.category == category
                )
                ranked = tuple(c.evidence.entity.id for c in candidates)
                relevant = {
                    e["record_id"]
                    for e in query["evidence"]
                    if e["file"]
                    == (
                        "data/Recipes.json"
                        if category == Category.RECIPE
                        else "data/structured_restaurant_data.json"
                    )
                }
                if "review" in plan.sources and category == Category.RESTAURANT:
                    relevant = set(query["relevant_ids"])
                r, n = recall(ranked, relevant, 20), ndcg(ranked, relevant, 5)
                if r is not None:
                    metrics["recall_at_20"].append(r)
                    metrics["ndcg_at_5"].append(n)
                known = [cuisines[category].get(identity) for identity in ranked[:5]]
                diversity = len({c for c in known if c}) / len(known) if known else None
                if diversity is not None:
                    metrics["cuisine_diversity_at_5"].append(diversity)
                entry["categories"][category.value] = {
                    "ranked_ids": ranked,
                    "recall_at_20": r,
                    "ndcg_at_5": n,
                    "cuisine_diversity_at_5": diversity,
                    "top5_components": [
                        {
                            "entity_id": c.evidence.entity.id,
                            "rrf_score": c.rrf_score,
                            "relevance": c.evidence.relevance,
                            "lexical_score": c.lexical_score,
                            "cosine_similarity": c.cosine_similarity,
                            "document_ids": [
                                x.document_id for x in c.evidence.citations
                            ],
                        }
                        for c in candidates[:5]
                    ],
                }
                violations["duplicate_entities"] += len(ranked) - len(set(ranked))
                async with sessions() as session:
                    for candidate in candidates:
                        entity_model = (
                            Restaurant if category == Category.RESTAURANT else Recipe
                        )
                        if (
                            await session.get(
                                entity_model, candidate.evidence.entity.id
                            )
                            is None
                        ):
                            violations["fabricated_entities"] += 1
                        if any(
                            a.constraint.strength == Strength.HARD
                            and a.state.value != "supported"
                            for a in candidate.assessments
                        ):
                            violations["hard_constraint_violations"] += 1
                        for citation in candidate.evidence.citations:
                            doc = await session.get(Document, citation.document_id)
                            record = (
                                await session.get(SourceRecord, doc.source_record_id)
                                if doc
                                else None
                            )
                            source = (
                                await session.get(Source, record.source_id)
                                if record
                                else None
                            )
                            if (
                                doc is None
                                or record is None
                                or source is None
                                or citation.excerpt != doc.text
                                or citation.source_id != source.id
                                or citation.record_id != record.record_id
                            ):
                                violations["fabricated_citations"] += 1
                                continue
                            if record.review_id:
                                review = await session.get(Review, record.review_id)
                                actual = review.restaurant_id if review else None
                                if (
                                    not review
                                    or review.demo_profile_id != plan.demo_profile_id
                                ):
                                    violations["review_scope_violations"] += 1
                            else:
                                actual = (
                                    record.restaurant_id
                                    if category == Category.RESTAURANT
                                    else record.recipe_id
                                )
                            if actual != citation.entity.id:
                                violations["fabricated_citations"] += 1
            rows.append(entry)
        assert not any(violations.values()), "Grounding or constraint violation"
        report = {
            "recorded_at": datetime.now(UTC).isoformat(),
            "labels_version": labels["version"],
            "labels_sha256": hashlib.sha256(args.queries.read_bytes()).hexdigest(),
            "label_scope": labels["label_scope"],
            "source_hashes": labels["source_hashes"],
            "model": encoder.model_id,
            "revision": encoder.revision,
            "dimension": 384,
            "device": "cpu",
            "fusion": {
                "rrf_k": 60,
                "lexical_weight": 0.5,
                "dense_weight": 0.5,
                "entity_aggregation": "maximum branch score; entity ranks before fusion",
                "normalization": "min-max per category; equal scores = 1",
            },
            "corpus": corpus,
            "versions": {
                **db_versions,
                **{
                    name: importlib.metadata.version(name)
                    for name in [
                        "sentence-transformers",
                        "transformers",
                        "torch",
                        "pgvector",
                        "sqlalchemy",
                    ]
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
            "model_load_ms": model_load_ms,
            "summary": {name: mean(values) for name, values in metrics.items()},
            "warm_latency_ms": {
                "median": median(latencies),
                "p95": sorted(latencies)[int(0.95 * (len(latencies) - 1))],
                "max": max(latencies),
            },
            "violations": violations,
            "usage": {"groq_calls": 0, "trend_searches": 0, "provider_tokens": 0},
            "queries": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "queries": len(rows),
                    "summary": report["summary"],
                    "warm_latency_ms": report["warm_latency_ms"],
                    "violations": violations,
                },
                indent=2,
            )
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(evaluate(parser.parse_args()))
