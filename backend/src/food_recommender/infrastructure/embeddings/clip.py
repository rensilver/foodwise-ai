"""Pinned, hash-verified offline CLIP on CPU. Never load at import/startup."""

import hashlib
import json
from pathlib import Path
from typing import Any

from food_recommender.infrastructure.media.images import decode_image
from food_recommender.retrieval.embedding_contracts import (
    CLIP_MODEL,
    CLIP_REVISION,
    validate_clip,
)

CLIP_FILES = (
    "config.json",
    "merges.txt",
    "preprocessor_config.json",
    "pytorch_model.bin",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)


class CLIPEncoder:
    def __init__(self, root: Path) -> None:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        manifest = json.loads((root / "foodwise-model.json").read_text())
        if (manifest["model"], manifest["revision"]) != (
            CLIP_MODEL,
            CLIP_REVISION,
        ) or set(manifest["files"]) != set(CLIP_FILES):
            raise ValueError("CLIP manifest mismatch")
        for filename in CLIP_FILES:
            path = root / filename
            if (
                path.is_symlink()
                or root.resolve() not in path.resolve().parents
                or hashlib.sha256(path.read_bytes()).hexdigest()
                != manifest["files"][filename]
            ):
                raise ValueError("CLIP model file hash mismatch")
        self.model: Any = (
            getattr(CLIPModel, "from_pretrained")(
                str(root),
                local_files_only=True,
                trust_remote_code=False,
                use_safetensors=False,
            )
            .to("cpu")
            .eval()
        )
        self.processor: Any = CLIPProcessor.from_pretrained(
            str(root), local_files_only=True, trust_remote_code=False
        )
        config = self.model.config
        if (
            config.projection_dim,
            config.text_config.max_position_embeddings,
            config.vision_config.image_size,
            config.vision_config.patch_size,
        ) != (512, 77, 224, 32):
            raise ValueError("Incompatible CLIP architecture")
        self.model_id, self.revision = CLIP_MODEL, CLIP_REVISION
        self.torch = torch

    def _vectors(self, features: Any) -> tuple[tuple[float, ...], ...]:
        # Transformers 5 returns a model output; earlier versions returned Tensor.
        values = (
            features.pooler_output if hasattr(features, "pooler_output") else features
        )
        values = values / values.norm(dim=-1, keepdim=True)
        result = tuple(tuple(float(v) for v in row) for row in values.tolist())
        for row in result:
            validate_clip(row, self.model_id, self.revision)
        return result

    def encode_images(self, images: tuple[bytes, ...]) -> tuple[tuple[float, ...], ...]:
        if not images:
            return ()
        decoded = [decode_image(data) for data in images]
        try:
            inputs = self.processor(images=decoded, return_tensors="pt")
            with self.torch.inference_mode():
                return self._vectors(self.model.get_image_features(**inputs))
        finally:
            for image in decoded:
                image.close()

    def encode_texts(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        if not texts:
            return ()
        if any(not t.strip() or len(t) > 2000 for t in texts):
            raise ValueError("Invalid CLIP text")
        inputs = self.processor(
            text=list(texts), return_tensors="pt", padding=True, truncation=False
        )
        if inputs["input_ids"].shape[1] > 77:
            raise ValueError("CLIP text exceeds token budget")
        with self.torch.inference_mode():
            return self._vectors(self.model.get_text_features(**inputs))
