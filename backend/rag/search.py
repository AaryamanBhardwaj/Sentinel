"""RAG search over the error-pattern corpus.

Precomputed embeddings stored as .npy, cosine similarity at query time.
No vector DB — the corpus fits in Lambda memory (~20 patterns, <1MB).

The module lazy-loads on first search call to avoid cold-start penalty
when the Lambda handles non-search requests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

from backend.rag.embedder import TfidfEmbedder

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus"

_patterns: Optional[list] = None
_embeddings: Optional[np.ndarray] = None
_embedder: Optional[TfidfEmbedder] = None


def _load():
    """Lazy-load the corpus, embeddings, and embedder."""
    global _patterns, _embeddings, _embedder

    with open(CORPUS_DIR / "patterns.json") as f:
        _patterns = json.load(f)

    _embeddings = np.load(CORPUS_DIR / "embeddings.npy")
    _embedder = TfidfEmbedder.load(CORPUS_DIR / "embedder.pkl")


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity between vector a (1xD) and matrix b (NxD)."""
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return (a_norm @ b_norm.T).flatten()


async def search(query: str, top_k: int = 3) -> list[dict]:
    """Embed the query, compute cosine similarity, return top-k patterns."""
    if _patterns is None:
        _load()

    query_vec = _embedder.embed([query])
    scores = _cosine_similarity(query_vec, _embeddings)

    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        score = float(scores[idx])
        if score < 0.05:
            continue
        p = _patterns[idx]
        results.append({
            "id": p["id"],
            "title": p["title"],
            "root_cause": p["root_cause"],
            "fix": p["fix"],
            "category": p["category"],
            "similarity": round(score, 4),
        })

    return results
