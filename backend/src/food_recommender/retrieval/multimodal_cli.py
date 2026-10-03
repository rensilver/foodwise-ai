"""Explicit local multimodal search using private media IDs and pinned CPU models."""

import argparse
import asyncio
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.application.contracts import multimodal_adapter
from food_recommender.composition import build_multimodal_retrieval
from food_recommender.domain.preferences import Constraint
from food_recommender.domain.values import Category, ConstraintKind, Origin, Strength
from food_recommender.infrastructure.clip_encoder import CLIPEncoder
from food_recommender.infrastructure.persistence import create_database_engine
from food_recommender.infrastructure.text_encoder import MiniLMEncoder
from food_recommender.retrieval.late_fusion import FusionWeights
from food_recommender.retrieval.models import TextPlan


async def execute(args: argparse.Namespace) -> int:
    weights = FusionWeights(args.text_weight, args.image_weight)
    text_encoder = (
        await asyncio.to_thread(MiniLMEncoder, args.minilm_root)
        if args.minilm_root and weights.text > 0 and not args.image_only
        else None
    )
    image_encoder = (
        await asyncio.to_thread(CLIPEncoder, args.clip_root)
        if args.clip_root and weights.image > 0
        else None
    )
    engine = create_database_engine(os.environ["DATABASE_URL"])
    try:
        service = build_multimodal_retrieval(
            async_sessionmaker(engine, expire_on_commit=False),
            text_encoder,
            image_encoder,
            Path(os.environ["MEDIA_ROOT"]),
            allow_catalog_queries=True,
        )
        plan = TextPlan(
            args.query,
            categories=tuple(Category(c) for c in args.category),
            sources=tuple(args.source),
            cuisine=args.cuisine,
            location=args.location,
            max_price_band=args.max_price_band,
            entity_ids=tuple(args.entity_id),
            demo_profile_id=args.demo_profile_id,
            constraints=tuple(
                Constraint(ConstraintKind.ALLERGEN, a, Strength.HARD, Origin.EXPLICIT)
                for a in args.hard_allergen
            ),
            limit=args.limit,
        )
        result = await service.run(
            plan,
            media_id=args.media_id,
            session_id=args.session_id,
            use_text=not args.image_only,
            weights=weights,
        )
        print(multimodal_adapter.dump_json(result, indent=2).decode())
        return 0 if result.status in ("success", "no_results") else 2
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="image query")
    parser.add_argument("--minilm-root", type=Path)
    parser.add_argument("--clip-root", type=Path)
    parser.add_argument(
        "--category",
        nargs="+",
        choices=("restaurant", "recipe"),
        default=["restaurant", "recipe"],
    )
    parser.add_argument(
        "--source",
        nargs="+",
        choices=("restaurant", "recipe", "review"),
        default=["restaurant", "recipe"],
    )
    parser.add_argument("--media-id")
    parser.add_argument("--session-id", type=UUID)
    parser.add_argument("--image-only", action="store_true")
    parser.add_argument("--cuisine")
    parser.add_argument("--location")
    parser.add_argument("--max-price-band", type=int)
    parser.add_argument("--demo-profile-id")
    parser.add_argument("--entity-id", action="append", default=[])
    parser.add_argument("--hard-allergen", action="append", default=[])
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--text-weight", type=float, default=0.6)
    parser.add_argument("--image-weight", type=float, default=0.4)
    args = parser.parse_args()
    if args.image_only and not args.media_id:
        parser.error("--image-only requires --media-id")
    raise SystemExit(asyncio.run(execute(args)))


if __name__ == "__main__":
    main()
