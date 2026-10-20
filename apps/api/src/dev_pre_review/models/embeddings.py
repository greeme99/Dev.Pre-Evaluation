"""Embedding provider protocol and deterministic reference implementation (FN-006, RET-001)."""

import hashlib
import math
from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicEmbeddingProvider:
    """Deterministic, reproducible text embedding provider for tests and offline processing."""

    def __init__(self, dimension: int = 64) -> None:
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_single(t) for t in texts]

    def _embed_single(self, text: str) -> list[float]:
        # Hash text into character n-grams and project into vector
        vec = [0.0] * self._dim
        clean = text.strip().lower()
        if not clean:
            return vec

        # Use character trigrams and token hashes
        tokens = clean.split()
        for i, token in enumerate(tokens):
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            vec[idx] += 1.0 / (1.0 + 0.1 * i)

        # Trigrams for Korean / subword similarity
        for i in range(len(clean) - 2):
            trigram = clean[i : i + 3]
            h = int(hashlib.md5(trigram.encode("utf-8")).hexdigest(), 16)  # noqa: S324
            idx = h % self._dim
            vec[idx] += 0.5

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec
