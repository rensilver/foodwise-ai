"""Rebuild the local Phase 0 inventories without reading any environment file."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REPORTS = ROOT / "evaluation" / "phase0"

COURSE_NOTEBOOKS = [
    "01_build_a_structured_generative_ai_application/01_Extract Structured JSON from Restaurant Text Using LLMs-v1.ipynb",
    "01_build_a_structured_generative_ai_application/Structure Text and Multimodal Data with LLMs(1).ipynb",
    "01_build_a_structured_generative_ai_application/M1L2_Process_Multimodal_Data_with_LLMs.ipynb",
    "02_design_a_multimodal_rag_system/M2L1_Lab.ipynb",
    "02_design_a_multimodal_rag_system/M2L2_Lab.ipynb",
    "02_design_a_multimodal_rag_system/M2L3_Lab.ipynb",
    "02_design_a_multimodal_rag_system/M2L3 DONE/M2L3_Lab.ipynb",
    "03_agents/M3L1_Design_Specialized_Agents.ipynb",
    "03_agents/M3L2_Implement_Multi_Agent_Systems.ipynb",
    "03_agents/originals/M3L2_Implement_Multi_Agent_Systems.ipynb",
    "03_agents/M3L3_Build_Chatbot_Interface.ipynb",
    "03_agents/originals/M3L3_Build_Chatbot_Interface.ipynb",
]
COURSE_SCRIPTS = [
    "01_build_a_structured_generative_ai_application/restaurant_data_management.py",
    "04_mcp/client.py",
]
DATA_ARTIFACTS = [
    "data/California-Culinary-Map.txt",
    "data/structured_restaurant_data.json",
    "data/Recipes.json",
    "data/augmented_food_recipe.json",
    "data/Synthetic-User-Reviews.json",
    "data/augmented_user_review.json",
    "data/review_image_placeholder.jpeg",
    "data/synthetic-recipe-images.zip",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(name: str, value: object) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def source_manifest() -> dict:
    paths = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").glob("*.pdf"))
    assert len(paths) == 12, "Expected 12 course assignment PDFs"
    records = []
    for role, names in (
        ("course_reference", paths),
        ("course_experiment", COURSE_NOTEBOOKS + COURSE_SCRIPTS),
        ("seed_data", DATA_ARTIFACTS),
        ("credential_excluded", ["03_agents/.env"]),
    ):
        for name in names:
            path = ROOT / name
            record = {"path": name, "role": role}
            if role == "credential_excluded":
                record["status"] = "excluded; hash intentionally omitted"
            elif path.is_file():
                record.update(status="present", bytes=path.stat().st_size, sha256=sha256(path))
                if name in COURSE_NOTEBOOKS and "M3L2_Implement_Multi_Agent_Systems" in name:
                    record["note"] = "local sanitized copy; original retained in source repository"
            elif name == "data/synthetic-recipe-images.zip":
                record.update(status="source ZIP was zero bytes; recovered archive unavailable")
            else:
                record["status"] = "missing"
            records.append(record)
    assert len(records) == 35
    result = {"baseline_artifacts": len(records), "records": records}
    write_json("source_manifest.json", result)
    return result


def normalize(value: str) -> str:
    value = value.replace("’", "'").replace("‘", "'")
    value = value.replace("'", "")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def word_match(needle: str, haystack: str) -> bool:
    return bool(needle and re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", haystack))


def match_score(record: dict, paragraph: str) -> int:
    text = normalize(paragraph)
    name = normalize(record["name"])
    if not word_match(name, text):
        return -100
    score = 100
    if word_match(normalize(record["location"]), text):
        score += 10
    score += 3 * sum(word_match(normalize(value), text) for value in record["signatures"])
    if re.search(r"(?<!\d)" + re.escape(str(record["rating"])) + r"\s*/\s*5", paragraph):
        score += 2
    if "Price range: " + "$" * record["price_range"] in paragraph:
        score += 2
    return score


def reconcile_restaurants() -> dict:
    content = (DATA / "California-Culinary-Map.txt").read_text()
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", content) if chunk.strip()]
    assert chunks[0].startswith("### ")
    paragraphs = chunks[1:]
    restaurants = json.loads((DATA / "structured_restaurant_data.json").read_text())
    assert len(paragraphs) == 210 and len(restaurants) == 204

    # Monotone alignment preserves source order and permits missing structured rows.
    n, m = len(restaurants), len(paragraphs)
    dp = [[-10**9] * (m + 1) for _ in range(n + 1)]
    trace = [[False] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        dp[0][j] = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i][j] = dp[i][j - 1]
            score = match_score(restaurants[i - 1], paragraphs[j - 1])
            candidate = dp[i - 1][j - 1] + score
            if score > 0 and candidate > dp[i][j]:
                dp[i][j] = candidate
                trace[i][j] = True
    assert dp[n][m] > 0, "Could not align all restaurant records"
    links = {}
    i, j = n, m
    while i:
        assert j, "Alignment ended before all structured records were mapped"
        if trace[i][j]:
            links[j] = restaurants[i - 1]
            i -= 1
        j -= 1
    rows = []
    for number, paragraph in enumerate(paragraphs, 1):
        record = links.get(number)
        row = {
            "paragraph": number,
            "source_sha256": hashlib.sha256(paragraph.encode()).hexdigest(),
            "source_excerpt": paragraph[:180],
            "status": "mapped" if record else "unresolved_structured_record",
            "itemId": record["itemId"] if record else None,
            "name": record["name"] if record else None,
        }
        if record:
            row["match_score"] = match_score(record, paragraph)
        rows.append(row)
    ids = [row["itemId"] for row in rows if row["itemId"] is not None]
    assert len(ids) == len(set(ids)) == 204
    by_name_location = {}
    for record in restaurants:
        key = (normalize(record["name"]), normalize(record["location"]))
        by_name_location.setdefault(key, []).append(record)
    potential_duplicates = [
        {
            "name": group[0]["name"],
            "location": group[0]["location"],
            "itemIds": [record["itemId"] for record in group],
            "price_ranges": [record["price_range"] for record in group],
            "ratings": [record["rating"] for record in group],
            "note": "Same normalized name and location; preserve both source IDs pending entity review.",
        }
        for group in by_name_location.values() if len(group) > 1
    ]
    result = {
        "source_paragraphs": len(paragraphs),
        "mapped": len(ids),
        "unresolved": len(paragraphs) - len(ids),
        "potential_duplicate_groups": potential_duplicates,
        "notes": "Unresolved rows require review and new stable IDs during ingestion; repeated names can denote distinct restaurants.",
        "rows": rows,
    }
    write_json("restaurant_reconciliation.json", result)
    return result


def validate_sources() -> dict:
    restaurants = json.loads((DATA / "structured_restaurant_data.json").read_text())
    recipes = json.loads((DATA / "Recipes.json").read_text())
    augmented_recipes = json.loads((DATA / "augmented_food_recipe.json").read_text())
    reviews = json.loads((DATA / "Synthetic-User-Reviews.json").read_text())
    augmented_reviews = json.loads((DATA / "augmented_user_review.json").read_text())
    restaurant_ids = [row["itemId"] for row in restaurants]
    recipe_ids = [row["id"] for row in recipes]
    review_ids = [row["reviewId"] for row in reviews]
    assert len(set(restaurant_ids)) == len(restaurant_ids) == 204
    assert len(set(recipe_ids)) == len(recipe_ids) == 109
    assert len(set(review_ids)) == len(review_ids) == 10
    assert {row["id"] for row in augmented_recipes} == set(recipe_ids)
    assert {row["reviewId"] for row in augmented_reviews} == set(review_ids)
    assert all(row["itemId"] in set(restaurant_ids) for row in reviews)
    refs = captions = 0
    for row in augmented_reviews:
        images = row["images"]
        assert len(images) <= 16384
        parsed = ast.literal_eval(images)
        assert isinstance(parsed, list) and all(isinstance(url, str) for url in parsed)
        refs += len(parsed)
        assert isinstance(row["image_captions"], list)
        captions += len(row["image_captions"])
        assert len(parsed) == len(row["image_captions"])
    result = {
        "restaurant_records": len(restaurants),
        "restaurant_ids_unique": True,
        "null_vibes": sum(row["vibe"] is None for row in restaurants),
        "recipe_records": len(recipes),
        "augmented_recipe_ids_match": True,
        "review_records": len(reviews),
        "augmented_review_ids_match": True,
        "synthetic_users": len({row["userId"] for row in reviews}),
        "review_image_references": refs,
        "review_image_captions": captions,
        "orphan_review_links": 0,
    }
    write_json("source_validation.json", result)
    return result


def media_manifest() -> dict:
    recipes = json.loads((DATA / "Recipes.json").read_text())
    expected = {row["id"] for row in recipes}
    image_dir = DATA / "synthetic_recipe_images"
    assert image_dir.is_dir()
    rows, failures = [], []
    for path in sorted(image_dir.iterdir()):
        if path.is_symlink():
            failures.append(f"symlink entry: {path.name}")
            continue
        if not path.is_file():
            failures.append(f"non-file entry: {path.name}")
            continue
        match = re.fullmatch(r"recipe([1-9][0-9]*)\.png", path.name)
        if not match:
            failures.append(f"unexpected filename: {path.name}")
            continue
        recipe_id = int(match.group(1))
        if recipe_id not in expected:
            failures.append(f"extra recipe ID: {recipe_id}")
        try:
            with Image.open(path) as image:
                image.verify()
            with Image.open(path) as image:
                image.load()
                assert image.format == "PNG"
                width, height = image.size
        except (UnidentifiedImageError, OSError, AssertionError) as error:
            failures.append(f"invalid PNG: {path.name}: {type(error).__name__}")
            continue
        rows.append({
            "recipe_id": recipe_id,
            "filename": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "format": "PNG",
            "width": width,
            "height": height,
        })
    ids = [row["recipe_id"] for row in rows]
    duplicates = sorted(value for value, count in Counter(ids).items() if count > 1)
    hash_duplicates = sorted(value for value, count in Counter(row["sha256"] for row in rows).items() if count > 1)
    result = {
        "recipe_count": len(expected),
        "decoded_images": len(rows),
        "missing_recipe_ids": sorted(expected - set(ids)),
        "duplicate_recipe_ids": duplicates,
        "duplicate_image_hashes": hash_duplicates,
        "failures": failures,
        "archive": validate_archive(rows),
        "review_images": "nine URL references are not recovered local files",
        "placeholder": "review_image_placeholder.jpeg is unlinked to any source entity",
        "rows": rows,
    }
    write_json("recipe_media_manifest.json", result)
    return result


def validate_archive(image_rows: list[dict]) -> dict:
    archive = DATA / "synthetic-recipe-images.zip"
    if not archive.exists():
        return {"status": "unavailable"}
    if not zipfile.is_zipfile(archive):
        raise ValueError("Recovered archive is not a ZIP file")
    by_name = {"synthetic_recipe_images/" + row["filename"]: row for row in image_rows}
    seen = set()
    total = 0
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.infolist()
        assert len(members) <= 200, "Archive has too many members"
        for member in members:
            parts = PurePosixPath(member.filename).parts
            if member.is_dir():
                assert parts == ("synthetic_recipe_images",), "Unexpected directory member"
                continue
            assert len(parts) == 2 and parts[0] == "synthetic_recipe_images", "Unsafe archive path"
            assert member.filename in by_name, "Unexpected archive image"
            assert member.filename not in seen, "Duplicate archive member"
            assert not member.flag_bits & 1, "Encrypted archive member"
            mode = (member.external_attr >> 16) & 0o170000
            assert mode in (0, 0o100000), "Nonregular archive member"
            assert member.file_size <= 10 * 1024 * 1024, "Oversized archive member"
            assert member.compress_size > 0, "Invalid compressed size"
            assert member.file_size <= member.compress_size * 100, "Excessive expansion ratio"
            total += member.file_size
            assert total <= 300 * 1024 * 1024, "Excessive archive expansion"
            digest = hashlib.sha256()
            length = 0
            with zipped.open(member) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
                    length += len(block)
            assert length == member.file_size, "Truncated archive member"
            assert digest.hexdigest() == by_name[member.filename]["sha256"], "Extracted image mismatch"
            seen.add(member.filename)
    assert seen == set(by_name), "Archive does not cover the extracted image set"
    return {
        "status": "validated",
        "filename": archive.name,
        "bytes": archive.stat().st_size,
        "sha256": sha256(archive),
        "image_members": len(seen),
        "uncompressed_bytes": total,
        "checks": ["ZIP structure", "bounded members and expansion", "safe paths", "regular files", "CRC", "byte-for-byte SHA-256 match to decoded PNGs"],
    }


def main() -> None:
    manifest = source_manifest()
    sources = validate_sources()
    restaurants = reconcile_restaurants()
    media = media_manifest()
    print(json.dumps({
        "source_artifacts": manifest["baseline_artifacts"],
        "sources": sources,
        "restaurants": {key: restaurants[key] for key in ("source_paragraphs", "mapped", "unresolved")},
        "media": {key: media[key] for key in ("recipe_count", "decoded_images", "missing_recipe_ids", "duplicate_recipe_ids", "failures")},
    }, indent=2))


if __name__ == "__main__":
    main()
