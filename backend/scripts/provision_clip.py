"""Explicit public pretrained download at an immutable revision; never runs in tests."""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

from food_recommender.infrastructure.embeddings.clip import CLIP_FILES
from food_recommender.retrieval.embedding_contracts import CLIP_MODEL, CLIP_REVISION


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for filename in CLIP_FILES:
        path = root / filename
        temporary = root / (filename + ".part")
        url = f"https://huggingface.co/{CLIP_MODEL}/resolve/{CLIP_REVISION}/{filename}"
        digest = hashlib.sha256()
        size = 0
        with (
            urllib.request.urlopen(url, timeout=60) as response,
            temporary.open("wb") as target,
        ):
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > 650 * 1024 * 1024:
                    raise ValueError("Model file exceeds limit")
                digest.update(chunk)
                target.write(chunk)
        temporary.replace(path)
        hashes[filename] = digest.hexdigest()
    (root / "foodwise-model.json").write_text(
        json.dumps(
            {"model": CLIP_MODEL, "revision": CLIP_REVISION, "files": hashes}, indent=2
        )
        + "\n"
    )
    print("Provisioned pinned CPU CLIP files and hash manifest.")


if __name__ == "__main__":
    main()
