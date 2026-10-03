"""CPU encoding is the only model dependency of text indexing/search."""

from typing import Protocol


class TextEncoder(Protocol):
    model_id: str
    revision: str
    max_tokens: int

    def offsets(self, text: str) -> tuple[tuple[int, int], ...]: ...
    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...
