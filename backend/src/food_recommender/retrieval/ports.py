"""CPU encoding is the only model dependency of text indexing/search."""

from typing import Literal, Protocol

from food_recommender.domain.values import Category
from food_recommender.retrieval.models import ImageHit, TextHit, TextPlan


class TextEncoder(Protocol):
    model_id: str
    revision: str
    max_tokens: int

    def offsets(self, text: str) -> tuple[tuple[int, int], ...]: ...
    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


class TextSearch(Protocol):
    async def search(
        self,
        plan: TextPlan,
        category: Category,
        branch: Literal["lexical", "dense"],
        vector: tuple[float, ...] | None = None,
        *,
        model: str,
        revision: str,
    ) -> tuple[TextHit, ...]: ...


class ImageEncoder(Protocol):
    model_id: str
    revision: str

    def encode_images(
        self, images: tuple[bytes, ...]
    ) -> tuple[tuple[float, ...], ...]: ...
    def encode_texts(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


class ImageSearch(Protocol):
    async def search(
        self,
        plan: TextPlan,
        category: Category,
        vector: tuple[float, ...],
        *,
        model: str,
        revision: str,
    ) -> tuple[ImageHit, ...]: ...
