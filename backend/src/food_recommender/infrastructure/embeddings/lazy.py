"""Load only explicitly provisioned local weights, on the first off-loop query."""

from pathlib import Path
from threading import Lock

from food_recommender.infrastructure.embeddings.clip import CLIPEncoder
from food_recommender.infrastructure.embeddings.minilm import MiniLMEncoder
from food_recommender.retrieval.embedding_contracts import (
    CLIP_MODEL,
    CLIP_REVISION,
    MINILM_MODEL,
    MINILM_REVISION,
)


class LazyMiniLM:
    model_id = MINILM_MODEL
    revision = MINILM_REVISION
    max_tokens = 254

    def __init__(self, root: Path) -> None:
        self.root = root
        self.encoder: MiniLMEncoder | None = None
        self.lock = Lock()

    def _get(self) -> MiniLMEncoder:
        with self.lock:
            if self.encoder is None:
                self.encoder = MiniLMEncoder(self.root)
            return self.encoder

    def offsets(self, text: str) -> tuple[tuple[int, int], ...]:
        return self._get().offsets(text)

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return self._get().encode(texts)


class LazyCLIP:
    model_id = CLIP_MODEL
    revision = CLIP_REVISION

    def __init__(self, root: Path) -> None:
        self.root = root
        self.encoder: CLIPEncoder | None = None
        self.lock = Lock()

    def _get(self) -> CLIPEncoder:
        with self.lock:
            if self.encoder is None:
                self.encoder = CLIPEncoder(self.root)
            return self.encoder

    def encode_texts(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return self._get().encode_texts(texts)

    def encode_images(self, images: tuple[bytes, ...]) -> tuple[tuple[float, ...], ...]:
        return self._get().encode_images(images)
