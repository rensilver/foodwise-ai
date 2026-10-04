"""Explicit, offline, revision-verified CPU MiniLM adapter; no import-time loads."""

import hashlib
import json
from pathlib import Path
from typing import Any

from food_recommender.retrieval.embedding_contracts import (
    MINILM_MODEL,
    MINILM_REVISION,
    validate_query,
)


class MiniLMEncoder:
    def __init__(self, root: Path) -> None:
        from sentence_transformers import SentenceTransformer

        manifest = json.loads((root / "foodwise-model.json").read_text())
        if (manifest["model"], manifest["revision"]) != (MINILM_MODEL, MINILM_REVISION):
            raise ValueError("Model manifest mismatch")
        for filename, expected in manifest["files"].items():
            path = root / filename
            if (
                root.resolve() not in path.resolve().parents
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                raise ValueError("Model file hash mismatch")
        self.model: Any = SentenceTransformer(
            str(root), device="cpu", local_files_only=True, trust_remote_code=False
        )
        if (
            self.model.get_embedding_dimension() != 384
            or self.model.max_seq_length != 256
        ):
            raise ValueError("Incompatible MiniLM encoder")
        self.model_id = MINILM_MODEL
        self.revision = MINILM_REVISION
        self.max_tokens = 256 - self.model.tokenizer.num_special_tokens_to_add(
            pair=False
        )

    def offsets(self, text: str) -> tuple[tuple[int, int], ...]:
        result = self.model.tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
            return_offsets_mapping=True,
        )
        return tuple((int(a), int(b)) for a, b in result["offset_mapping"])

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if any(len(self.offsets(text)) > self.max_tokens for text in texts):
            raise ValueError("Input exceeds MiniLM token budget")
        if not texts:
            return ()
        vectors = self.model.encode(
            list(texts),
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        result = tuple(tuple(float(value) for value in vector) for vector in vectors)
        for values in result:
            validate_query(values, self.model_id, self.revision)
        return result
