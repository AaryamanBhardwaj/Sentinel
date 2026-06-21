"""Offline embedding pipeline — run once to precompute corpus embeddings.

Usage:
    python3 -m backend.rag.embed                  # TF-IDF (default, no API key)
    python3 -m backend.rag.embed --backend voyage  # Voyage AI (needs VOYAGE_API_KEY)

Reads corpus/patterns.json, computes embeddings, writes:
    corpus/embeddings.npy    — embedding matrix (N x D)
    corpus/embedder.pkl      — serialized embedder (for query-time embedding)
"""

import argparse
import json
from pathlib import Path

import numpy as np

from backend.rag.embedder import get_embedder, TfidfEmbedder

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus"


def build_searchable_text(pattern: dict) -> str:
    """Combine pattern fields into a single string for embedding.

    Concatenating title + pattern + root_cause + tags gives the embedder
    signal from both the symptom (what the user sees) and the diagnosis
    (what the user is looking for).
    """
    parts = [
        pattern["title"],
        pattern["pattern"],
        pattern["root_cause"],
        pattern.get("fix", ""),
        " ".join(pattern.get("tags", [])),
    ]
    return " ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="Precompute corpus embeddings")
    parser.add_argument("--backend", default="tfidf", choices=["tfidf", "voyage"])
    args = parser.parse_args()

    patterns_path = CORPUS_DIR / "patterns.json"
    with open(patterns_path) as f:
        patterns = json.load(f)

    print(f"Loaded {len(patterns)} patterns from {patterns_path}")

    texts = [build_searchable_text(p) for p in patterns]
    embedder = get_embedder(args.backend)

    if isinstance(embedder, TfidfEmbedder):
        matrix = embedder.fit_embed(texts)
    else:
        matrix = embedder.embed(texts)

    embeddings_path = CORPUS_DIR / "embeddings.npy"
    embedder_path = CORPUS_DIR / "embedder.pkl"

    np.save(embeddings_path, matrix)
    embedder.save(embedder_path)

    print(f"Embeddings shape: {matrix.shape}")
    print(f"Saved to: {embeddings_path}")
    print(f"Embedder saved to: {embedder_path}")


if __name__ == "__main__":
    main()
