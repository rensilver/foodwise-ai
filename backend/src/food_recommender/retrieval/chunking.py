"""Lossless character ranges at encoder token boundaries, excluding specials."""

from collections.abc import Callable


def chunks(
    text: str,
    tokenize: Callable[[str], tuple[tuple[int, int], ...]],
    *,
    max_tokens: int = 254,
) -> tuple[tuple[int, int], ...]:
    if max_tokens < 1:
        raise ValueError("Token budget must be positive")
    if not text:
        return ()
    tokens = tokenize(text)
    previous = 0
    for start, end in tokens:
        if not previous <= start < end <= len(text):
            raise ValueError("Invalid tokenizer offsets")
        previous = end
    if not tokens:
        raise ValueError("Nonempty source has no tokens")
    result = []
    start = 0
    for position in range(max_tokens, len(tokens), max_tokens):
        end = tokens[position][0]
        result.append((start, end))
        start = end
    result.append((start, len(text)))
    # Validate re-tokenized excerpts, since subword splits can change boundaries.
    if any(len(tokenize(text[a:b])) > max_tokens for a, b in result):
        raise ValueError("Chunk exceeds encoder token budget")
    return tuple(result)
