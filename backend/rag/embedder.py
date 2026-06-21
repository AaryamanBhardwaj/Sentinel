"""Embedding backends for the RAG layer.

Supports multiple backends via a common protocol:
  - "tfidf": TF-IDF vectors via scikit-learn. No API key needed. Good enough
    for a small corpus of error patterns where exact keyword overlap matters.
  - "voyage": Voyage AI embeddings (voyage-3-lite). Semantic search, requires
    VOYAGE_API_KEY.

The TF-IDF backend is the default so the project runs out of the box.
In production you'd use Voyage for better semantic matching.
"""

from __future__ import annotations

import json
import os
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> np.ndarray: ...
    def save(self, path: Path) -> None: ...

    @classmethod
    def load(cls, path: Path) -> "Embedder": ...


class TfidfEmbedder:
    """TF-IDF vectorizer — no API calls, deterministic, fast.

    Good fit here because error patterns are keyword-heavy: "OutOfMemoryError"
    should match "OutOfMemoryError", and TF-IDF does that reliably.
    """

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=2048,
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        self._fitted = False

    def fit_embed(self, texts: list[str]) -> np.ndarray:
        matrix = self.vectorizer.fit_transform(texts).toarray().astype(np.float32)
        self._fitted = True
        return matrix

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Vectorizer not fitted — run embed.py first")
        return self.vectorizer.transform(texts).toarray().astype(np.float32)

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self.vectorizer, f)

    @classmethod
    def load(cls, path: Path) -> "TfidfEmbedder":
        instance = cls.__new__(cls)
        with open(path, "rb") as f:
            instance.vectorizer = pickle.load(f)
        instance._fitted = True
        return instance


class VoyageEmbedder:
    """Voyage AI embeddings — semantic search, requires API key."""

    def __init__(self, model: str = "voyage-3-lite"):
        import voyageai
        self.client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])
        self.model = model

    def embed(self, texts: list[str]) -> np.ndarray:
        result = self.client.embed(texts, model=self.model)
        return np.array(result.embeddings, dtype=np.float32)

    def save(self, path: Path) -> None:
        with open(path, "w") as f:
            json.dump({"backend": "voyage", "model": self.model}, f)

    @classmethod
    def load(cls, path: Path) -> "VoyageEmbedder":
        with open(path) as f:
            config = json.load(f)
        return cls(model=config.get("model", "voyage-3-lite"))


def get_embedder(backend: str = "tfidf") -> TfidfEmbedder | VoyageEmbedder:
    if backend == "voyage":
        return VoyageEmbedder()
    return TfidfEmbedder()
