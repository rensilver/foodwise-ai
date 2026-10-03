"""Seed planning preserves all original artifacts and reports every source gap."""

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from food_recommender.domain.catalog import (
    DocumentData,
    MediaData,
    RestaurantData,
    SourceData,
)
from food_recommender.ingestion.adapters import (
    INGESTION_VERSION,
    SourceError,
    adapt_recipe,
    adapt_restaurant,
    adapt_review,
    digest,
    normalize,
)
from food_recommender.ingestion.captions import supplied_captions
from food_recommender.ingestion.extraction import RestaurantFields
from food_recommender.ingestion.image_lists import parse_images
from food_recommender.ingestion.images import ArchiveReport, PreparedImage
from food_recommender.ingestion.merge import merge_records
from food_recommender.ingestion.models import SeedItem
from food_recommender.ingestion.reconciliation import read_paragraphs, reconcile


@dataclass(frozen=True)
class Artifact:
    source: SourceData
    content: bytes


def artifact(path: Path, logical_id: str) -> Artifact:
    if not path.is_file() or path.stat().st_size > 512 * 1024 * 1024:
        raise SourceError(path.name, "?", "Missing or oversized source file")
    content = path.read_bytes()
    content_hash = hashlib.sha256(content).hexdigest()
    locator = f"data/{path.name}"
    return Artifact(
        SourceData(
            id=digest([logical_id, locator, content_hash]),
            logical_source_id=logical_id,
            locator_kind="file",
            locator=locator,
            content_hash=content_hash,
        ),
        content,
    )


def json_records(item: Artifact) -> list[dict[str, Any]]:
    try:
        if len(item.content) > 32 * 1024 * 1024:
            raise ValueError()
        data = json.loads(item.content)
        if (
            not isinstance(data, list)
            or len(data) > 10000
            or any(not isinstance(row, dict) for row in data)
        ):
            raise ValueError()
        return data
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise SourceError(
            item.source.locator, "?", "Malformed JSON record array"
        ) from None


def source_record(
    source: SourceData,
    category: str,
    record_id: str,
    *,
    raw: dict[str, Any] | None = None,
    text: str | None = None,
    attribution: str = "source",
) -> dict[str, Any]:
    return {
        "id": digest([source.id, category, record_id]),
        "source_id": source.id,
        "record_type": category,
        "record_id": record_id,
        "content_hash": digest(raw if raw is not None else text),
        "ingestion_version": INGESTION_VERSION,
        "attribution": attribution,
        "raw_payload": raw,
        "raw_text": text,
    }


def caption_document(
    record: dict[str, Any], text: str, *, media_id: str | None = None
) -> DocumentData:
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return DocumentData(
        id=digest([record["id"], "caption", media_id, content_hash]),
        source_record_id=record["id"],
        kind="image_caption",
        text=text,
        media_id=media_id,
        content_hash=content_hash,
        ingestion_version=INGESTION_VERSION,
        attribution="imported",
    )


@dataclass
class SeedPlan:
    items: list[SeedItem]
    issues: list[dict[str, Any]]
    metadata: dict[str, Any]
    recipe_references: dict[str, str]
    review_references: dict[str, tuple[str, ...]]

    def issue(
        self, source: str, record_id: object, reason: str, status: str = "rejected"
    ) -> None:
        self.issues.append(
            {
                "source": source,
                "record_id": str(record_id),
                "reason": reason,
                "status": status,
            }
        )


def load_seed(
    data_root: Path, mapping_path: Path, accepted_path: Path | None = None
) -> SeedPlan:
    plan = SeedPlan([], [], {}, {}, {})
    artifacts: dict[str, Artifact] = {}
    records: dict[str, list[dict[str, Any]]] = {}
    for filename, logical_id in [
        ("structured_restaurant_data.json", "course-restaurants"),
        ("Recipes.json", "course-recipes"),
        ("augmented_food_recipe.json", "course-recipes"),
        ("Synthetic-User-Reviews.json", "course-reviews"),
        ("augmented_user_review.json", "course-reviews"),
    ]:
        try:
            file_artifact = artifact(data_root / filename, logical_id)
            artifacts[filename] = file_artifact
            records[filename] = json_records(file_artifact)
        except SourceError as error:
            plan.issue(error.source, error.record_id, error.reason)
            records[filename] = []
    plan.metadata["sources"] = [
        {"locator": value.source.locator, "content_hash": value.source.content_hash}
        for value in artifacts.values()
    ]
    restaurant_ids = set()
    groups: dict[tuple[str | None, str | None], list[str]] = defaultdict(list)
    for raw in records["structured_restaurant_data.json"]:
        try:
            adapted = adapt_restaurant(raw, "structured_restaurant_data.json")
            if adapted.data.id in restaurant_ids:
                raise SourceError(
                    adapted.locator, adapted.data.id, "Duplicate restaurant ID"
                )
            restaurant_ids.add(adapted.data.id)
            if (
                isinstance(adapted.data, RestaurantData)
                and raw.get("price_range") is not None
                and adapted.data.price_band is None
            ):
                plan.issue(
                    adapted.locator,
                    adapted.data.id,
                    "Unsupported legacy price range retained as unknown",
                    "unresolved",
                )
            if isinstance(adapted.data, RestaurantData):
                groups[
                    (normalize(adapted.data.name), adapted.data.normalized_location)
                ].append(adapted.data.id)
            original = artifacts[adapted.locator].source
            record = source_record(original, "restaurant", adapted.data.id, raw=raw)
            plan.items.append(
                SeedItem(adapted.data, (original,), (record,), inputs=(raw,))
            )
        except SourceError as error:
            plan.issue(error.source, error.record_id, error.reason)
    plan.metadata["duplicate_name_location_groups"] = [
        {
            "name": name,
            "location": location,
            "ids": ids,
            "decision": "preserve_source_ids_pending_entity_review",
        }
        for (name, location), ids in groups.items()
        if len(ids) > 1
    ]
    try:
        raw_map = artifact(
            data_root / "California-Culinary-Map.txt", "course-restaurants"
        )
        rows = json.loads(mapping_path.read_text())["rows"]
        accepted = (
            {} if accepted_path is None else json.loads(accepted_path.read_text())
        )
        mappings = reconcile(
            read_paragraphs(raw_map.content.decode()), rows, restaurant_ids, accepted
        )
        plan.metadata["sources"].append(
            {
                "locator": raw_map.source.locator,
                "content_hash": raw_map.source.content_hash,
            }
        )
        plan.metadata["paragraph_mappings"] = [
            {
                "paragraph": item.paragraph,
                "content_hash": item.content_hash,
                "status": item.status,
                "entity_id": item.entity_id,
            }
            for item in mappings
        ]
        positions = {item.data.id: index for index, item in enumerate(plan.items)}
        for mapping in mappings:
            if mapping.entity_id is None:
                plan.issue(
                    raw_map.source.locator,
                    mapping.paragraph,
                    "No accepted structured record",
                    "unresolved",
                )
                continue
            record = source_record(
                raw_map.source, "restaurant", str(mapping.paragraph), text=mapping.text
            )
            if mapping.status == "accepted_addition":
                try:
                    fields = RestaurantFields.model_validate(
                        mapping.accepted_fields
                    ).model_dump()
                    for field_key in ("signatures", "shortcomings"):
                        if fields[field_key] is not None:
                            fields[field_key] = tuple(fields[field_key])
                    data = RestaurantData(
                        id=mapping.entity_id,
                        source_id="course-restaurants",
                        source_record_id=f"paragraph:{mapping.content_hash}",
                        description=mapping.text,
                        normalized_cuisine=normalize(fields["cuisine"]),
                        normalized_location=normalize(fields["location"]),
                        **fields,
                    )
                    plan.items.append(
                        SeedItem(
                            data,
                            (raw_map.source,),
                            (record,),
                            inputs=(mapping.text, mapping.accepted_fields),
                        )
                    )
                    restaurant_ids.add(data.id)
                except (ValidationError, ValueError):
                    plan.issue(
                        "accepted additions",
                        mapping.paragraph,
                        "Invalid accepted restaurant fields",
                    )
            else:
                index = positions[mapping.entity_id]
                item = plan.items[index]
                if not isinstance(item.data, RestaurantData):
                    raise SourceError(
                        "restaurant mapping",
                        mapping.paragraph,
                        "Mapping category mismatch",
                    )
                plan.items[index] = replace(
                    item,
                    data=replace(item.data, description=mapping.text),
                    sources=(*item.sources, raw_map.source),
                    records=(*item.records, record),
                    inputs=(*item.inputs, mapping.text),
                )
    except (SourceError, ValueError, OSError, KeyError, TypeError) as error:
        plan.issue(
            "restaurant mapping",
            "?",
            error.reason
            if isinstance(error, SourceError)
            else "Invalid or missing mapping/acceptance source",
        )
    for base, augmented, identity, extra, adapter in [
        (
            "Recipes.json",
            "augmented_food_recipe.json",
            "id",
            {"image_description"},
            adapt_recipe,
        ),
        (
            "Synthetic-User-Reviews.json",
            "augmented_user_review.json",
            "reviewId",
            {"image_captions"},
            adapt_review,
        ),
    ]:
        # Join individual identities so one conflict cannot silently discard the
        # rest of the corpus. Every duplicate/orphan is separately reported.
        enriched: dict[object, list[dict[str, Any]]] = defaultdict(list)
        for row in records[augmented]:
            key = row.get(identity)
            if type(key) is not int:
                plan.issue(augmented, "?", "Invalid identity")
            else:
                enriched[key].append(row)
        seen: set[int] = set()
        for raw in records[base]:
            key = raw.get(identity)
            try:
                if type(key) is not int or key in seen:
                    raise SourceError(base, key, "Invalid or duplicate identity")
                seen.add(key)
                merged = merge_records(
                    [raw],
                    enriched.pop(key, []),
                    identity=identity,
                    enrichment=extra,
                    base_source=base,
                    augmented_source=augmented,
                )[0]
                adapted = adapter(merged.payload, base)
                if (
                    base == "Synthetic-User-Reviews.json"
                    and str(raw.get("itemId")) not in restaurant_ids
                ):
                    raise SourceError(base, key, "Unknown restaurant reference")
                sources = tuple(
                    artifacts[locator].source for locator, _ in merged.sources
                )
                source_records = tuple(
                    source_record(
                        artifacts[locator].source,
                        "recipe" if base == "Recipes.json" else "review",
                        str(key),
                        raw=payload,
                    )
                    for locator, payload in merged.sources
                )
                references: tuple[str, ...]
                if base == "Recipes.json":
                    references = (f"recipe{key}.png",)
                    plan.recipe_references[str(key)] = references[0]
                else:
                    references = parse_images(merged.payload.get("images"), base, key)
                    plan.review_references[str(key)] = references
                captions, gaps = supplied_captions(
                    merged.payload, references, source=augmented, record_id=key
                )
                documents = tuple(
                    caption_document(source_records[-1], caption.text)
                    for caption in captions
                )
                for reference in gaps:
                    plan.issue(
                        augmented, key, f"Caption absent for {reference}", "unresolved"
                    )
                plan.items.append(
                    SeedItem(
                        adapted.data,
                        sources,
                        source_records,
                        documents,
                        inputs=tuple(payload for _, payload in merged.sources),
                    )
                )
            except SourceError as error:
                plan.issue(error.source, error.record_id, error.reason)
        for key, orphan_rows in enriched.items():
            for _ in orphan_rows:
                plan.issue(augmented, key, "Enrichment has no accepted base identity")
    return plan


def attach_image(
    item: SeedItem,
    image: PreparedImage,
    original_locator: str,
    source: SourceData,
    *,
    image_record_id: str,
    caption_text: str | None = None,
) -> SeedItem:
    record = source_record(
        source,
        item.category,
        image_record_id,
        raw={
            "original_locator": original_locator,
            "original_image_hash": image.input_hash,
            "caption_source_record": item.records[-1]["id"] if caption_text else None,
        },
    )
    media_id = digest([record["id"], image.content_hash])
    media = MediaData(
        id=media_id,
        source_record_id=record["id"],
        storage_key=image.storage_key,
        mime_type="image/png",
        byte_size=image.byte_size,
        width=image.width,
        height=image.height,
        original_locator=original_locator,
        content_hash=image.content_hash,
        ingestion_version=INGESTION_VERSION,
        attribution="imported",
        input_hash=image.input_hash,
    )
    documents = item.documents
    if caption_text is not None:
        # Keep the source-backed caption once, now explicitly attached to media.
        documents = tuple(
            document for document in documents if document.text != caption_text
        ) + (caption_document(record, caption_text, media_id=media_id),)
    sources = (
        item.sources
        if any(value.id == source.id for value in item.sources)
        else (*item.sources, source)
    )
    return replace(
        item,
        sources=sources,
        records=(*item.records, record),
        documents=documents,
        media=(*item.media, media),
    )


def attach_recipe_archive(
    plan: SeedPlan, report: ArchiveReport, archive_source: SourceData
) -> None:
    for index, item in enumerate(plan.items):
        if item.category == "recipe" and item.data.id in report.images:
            caption = item.documents[0].text if item.documents else None
            plan.items[index] = attach_image(
                item,
                report.images[item.data.id],
                f"{archive_source.locator}#recipe{item.data.id}.png",
                archive_source,
                image_record_id=item.data.id,
                caption_text=caption,
            )
    for missing in report.missing:
        plan.issue(
            archive_source.locator, missing, "Recipe image missing", "unresolved"
        )
    for extra in report.extra:
        plan.issue(archive_source.locator, extra, "Image has no recipe", "unresolved")
    plan.metadata["recipe_archive"] = {
        "content_hash": archive_source.content_hash,
        "matched": len(report.images),
        "missing": list(report.missing),
        "extra": list(report.extra),
    }
