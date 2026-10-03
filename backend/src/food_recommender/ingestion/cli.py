"""Run explicit seed imports and extraction previews; never import on startup."""

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.domain.catalog import SourceData
from food_recommender.infrastructure.groq_ingestion import GroqStructuredInference
from food_recommender.infrastructure.ingestion import PostgresIngestionStore
from food_recommender.infrastructure.persistence import create_database_engine
from food_recommender.ingestion.adapters import SourceError, digest
from food_recommender.ingestion.extraction import (
    ExtractionService,
    RecipeFields,
    RestaurantFields,
    atomic_json,
)
from food_recommender.ingestion.images import (
    CourseDownloader,
    prepare_image,
    recipe_archive,
)
from food_recommender.ingestion.runner import ImportRunner
from food_recommender.ingestion.seed import (
    Artifact,
    SeedPlan,
    artifact,
    attach_image,
    attach_recipe_archive,
    load_seed,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


async def review_media(
    plan: SeedPlan, media_root: Path, cache_root: Path, *, download: bool
) -> None:
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        downloader = CourseDownloader(client)
        for index, item in enumerate(plan.items):
            if item.category != "review":
                continue
            references = plan.review_references[item.data.id]
            # Source payloads retain reference ordering even when captions are absent.
            raw = item.inputs[-1]
            captions = raw.get("image_captions", [])
            for number, locator in enumerate(references):
                path = cache_root / f"{digest(locator)}.bin"
                try:
                    if path.is_file() and path.stat().st_size <= 10 * 1024 * 1024:
                        content = await asyncio.to_thread(path.read_bytes)
                    elif download:
                        content = await downloader.download(locator)
                    else:
                        plan.issue(
                            "review media",
                            item.data.id,
                            f"Image unavailable: {locator}",
                            "unresolved",
                        )
                        continue
                    image = await asyncio.to_thread(
                        prepare_image,
                        content,
                        media_root,
                        namespace=f"course-review:{item.data.id}:{number}",
                    )
                    if not path.is_file():
                        cache_root.mkdir(parents=True, exist_ok=True)
                        temporary = path.with_suffix(".pending")
                        await asyncio.to_thread(temporary.write_bytes, content)
                        await asyncio.to_thread(temporary.replace, path)
                    content_hash = hashlib.sha256(content).hexdigest()
                    source = SourceData(
                        id=digest(["course-reviews", locator, content_hash]),
                        logical_source_id="course-reviews",
                        locator_kind="url",
                        locator=locator,
                        content_hash=content_hash,
                    )
                    caption = captions[number] if number < len(captions) else None
                    item = attach_image(
                        item,
                        image,
                        locator,
                        source,
                        image_record_id=f"{item.data.id}:{number}",
                        caption_text=caption,
                    )
                except (SourceError, OSError) as error:
                    plan.issue(
                        "review media",
                        item.data.id,
                        error.reason
                        if isinstance(error, SourceError)
                        else "Media storage failed",
                        "unresolved",
                    )
            plan.items[index] = item


async def import_seed(args: argparse.Namespace, environment: dict[str, Any]) -> int:
    if not environment.get("DATABASE_URL"):
        raise ValueError("Set DATABASE_URL explicitly; apply Alembic migrations first")
    media_root = Path(args.media_root or environment.get("MEDIA_ROOT", ""))
    if (
        not media_root.is_absolute()
        or media_root == Path("/")
        or ".." in media_root.parts
    ):
        raise ValueError("Set an absolute non-root MEDIA_ROOT without traversal")
    plan = await asyncio.to_thread(
        load_seed, args.data_root, args.mapping, args.accepted
    )
    try:
        archive: Artifact = await asyncio.to_thread(
            artifact, args.recipe_zip, "course-recipes"
        )
        recipe_ids = {item.data.id for item in plan.items if item.category == "recipe"}
        report = await asyncio.to_thread(
            recipe_archive, args.recipe_zip, recipe_ids, media_root
        )
        attach_recipe_archive(plan, report, archive.source)
    except SourceError as error:
        plan.issue(error.source, error.record_id, error.reason)
        for recipe_id in plan.recipe_references:
            plan.issue(
                "recipe media", recipe_id, "Recipe image unavailable", "unresolved"
            )
    await review_media(
        plan,
        media_root,
        args.report.parent / "downloads",
        download=args.download_review_images,
    )
    engine = create_database_engine(environment["DATABASE_URL"])
    try:
        result = await ImportRunner(
            PostgresIngestionStore(async_sessionmaker(engine, expire_on_commit=False)),
            args.report,
        ).run(plan.items, issues=plan.issues, metadata=plan.metadata)
    finally:
        await engine.dispose()
    print(json.dumps({"status": result["status"], "totals": result["totals"]}))
    return 2 if result["totals"]["rejected"] else 0


async def preview(args: argparse.Namespace, environment: dict[str, Any]) -> int:
    if not environment.get("GROQ_API_KEY"):
        raise ValueError("Set a fresh GROQ_API_KEY to explicitly enable extraction")
    text = args.input.read_text()
    async with httpx.AsyncClient(trust_env=False) as client:
        inference = GroqStructuredInference(
            client,
            SecretStr(environment["GROQ_API_KEY"]),
            environment.get("GROQ_MODEL") or "qwen/qwen3.8-27b",
        )
        service = ExtractionService(inference, args.output.parent / "quarantine")
        result = await service.preview(
            text,
            RestaurantFields if args.category == "restaurant" else RecipeFields,
            source=args.input.name,
            record_id=digest(text),
        )
    await asyncio.to_thread(atomic_json, args.output, result.model_dump())
    print(json.dumps({"status": result.status, "attempts": result.attempts}))
    return 0 if result.status == "validated" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file", type=Path, help="Explicit dotenv file; never prints its values"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    seed = commands.add_parser(
        "import", help="Validate and upsert the seed corpus; no provider inference"
    )
    seed.add_argument("--data-root", type=Path, default=REPOSITORY_ROOT / "data")
    seed.add_argument(
        "--mapping",
        type=Path,
        default=REPOSITORY_ROOT / "evaluation/phase0/restaurant_reconciliation.json",
    )
    seed.add_argument("--accepted", type=Path)
    seed.add_argument(
        "--recipe-zip",
        type=Path,
        default=REPOSITORY_ROOT / "data/synthetic-recipe-images.zip",
    )
    seed.add_argument("--media-root", type=str)
    seed.add_argument(
        "--report",
        type=Path,
        default=REPOSITORY_ROOT / ".local-tmp/ingestion/manifest.json",
    )
    seed.add_argument(
        "--download-review-images",
        action="store_true",
        help="Fetch only approved course-host review images over HTTPS",
    )
    extraction = commands.add_parser(
        "preview", help="Opt-in Groq extraction, without catalog writes"
    )
    extraction.add_argument(
        "--category", choices=["restaurant", "recipe"], required=True
    )
    extraction.add_argument("--input", type=Path, required=True)
    extraction.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.env_file is not None and not args.env_file.is_file():
            raise ValueError("Selected environment file is missing")
        environment = {
            **({} if args.env_file is None else dotenv_values(args.env_file)),
            **os.environ,
        }
        return asyncio.run(
            import_seed(args, environment)
            if args.command == "import"
            else preview(args, environment)
        )
    except (ValueError, OSError) as error:
        print(
            error.reason
            if isinstance(error, SourceError)
            else "Invalid ingestion input/configuration; check explicit files, DATABASE_URL and MEDIA_ROOT"
        )
        return 2
    except Exception:
        print(
            "Import unavailable or interrupted; inspect the report and retry after restoring dependencies"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
