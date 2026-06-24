"""Local sentence-transformer embeddings (all-MiniLM-L6-v2, 384-dim)."""
from __future__ import annotations

import hashlib
from typing import Protocol

EMBEDDING_DIM = 384
MODEL_NAME = "all-MiniLM-L6-v2"


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    """Lazy-loaded MiniLM embedder — no external API."""

    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        model = self._load()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()


class DeterministicEmbedder:
    """Fast deterministic vectors for unit tests (no model download)."""

    def embed(self, text: str) -> list[float]:
        seed = hashlib.sha256(text.encode()).digest()
        floats: list[float] = []
        for i in range(EMBEDDING_DIM):
            chunk = hashlib.sha256(seed + i.to_bytes(4, "big")).digest()
            val = int.from_bytes(chunk[:4], "big") / (2**32) * 2.0 - 1.0
            floats.append(val)
        norm = sum(x * x for x in floats) ** 0.5 or 1.0
        return [x / norm for x in floats]
