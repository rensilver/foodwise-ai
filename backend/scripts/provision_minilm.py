"""Explicit public pretrained download; never runs during startup or tests."""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

from food_recommender.retrieval.embedding_contracts import MINILM_MODEL, MINILM_REVISION

FILES = (
    "config.json",
    "config_sentence_transformers.json",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
    "1_Pooling/config.json",
    "model.safetensors",
)


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for filename in FILES:
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/{MINILM_MODEL}/resolve/{MINILM_REVISION}/{filename}"
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read(128 * 1024 * 1024)
        path.write_bytes(data)
        hashes[filename] = hashlib.sha256(data).hexdigest()
    (root / "foodwise-model.json").write_text(
        json.dumps(
            {"model": MINILM_MODEL, "revision": MINILM_REVISION, "files": hashes},
            indent=2,
        )
        + "\n"
    )
    print("Provisioned pinned CPU MiniLM files and hash manifest.")


if __name__ == "__main__":
    main()
