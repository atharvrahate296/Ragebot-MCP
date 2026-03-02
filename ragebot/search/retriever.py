"""
Context Retriever - Semantic search over indexed project files.
Uses FAISS/cosine similarity to find relevant chunks.
"""
from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ragebot.search.embedder import Embedder
    from ragebot.storage.db import Database


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class ContextRetriever:
    def __init__(self, embedder: "Embedder", db: "Database", top_k: int = 5):
        self.embedder = embedder
        self.db = db
        self.top_k = top_k
        self._faiss_index = None
        self._faiss_metadata: list[dict] = []

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict]:
        """Retrieve the most relevant chunks for a query."""
        k = top_k or self.top_k
        query_embedding = self.embedder.embed(query)

        # Try FAISS first
        try:
            results = self._faiss_retrieve(query_embedding, k)
            if results:
                return results
        except Exception:
            pass

        # Fallback: brute-force cosine similarity via DB
        return self._brute_force_retrieve(query_embedding, k)

    def build_faiss_index(self):
        """Build a FAISS index from all stored embeddings."""
        try:
            import faiss
            import numpy as np

            chunks = self.db.get_all_chunks()
            if not chunks:
                return

            embeddings = []
            self._faiss_metadata = []
            for chunk in chunks:
                emb = json.loads(chunk["embedding"])
                if emb:
                    embeddings.append(emb)
                    self._faiss_metadata.append(chunk)

            if not embeddings:
                return

            matrix = np.array(embeddings, dtype="float32")
            dim = matrix.shape[1]
            self._faiss_index = faiss.IndexFlatIP(dim)  # Inner product (cosine with normalized)
            faiss.normalize_L2(matrix)
            self._faiss_index.add(matrix)

        except ImportError:
            self._faiss_index = None

    def _faiss_retrieve(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """Retrieve using FAISS index."""
        if self._faiss_index is None:
            self.build_faiss_index()
        if self._faiss_index is None:
            return []

        import numpy as np
        import faiss

        q = np.array([query_embedding], dtype="float32")
        faiss.normalize_L2(q)
        scores, indices = self._faiss_index.search(q, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._faiss_metadata):
                continue
            chunk = self._faiss_metadata[idx]
            meta = json.loads(chunk.get("metadata", "{}")) if chunk.get("metadata") else {}
            results.append({
                "file_path": chunk["file_path"],
                "content": chunk["content"],
                "score": float(score),
                "file_type": meta.get("type", "unknown"),
                "summary": meta.get("summary", ""),
                "functions": meta.get("functions", []),
                "classes": meta.get("classes", []),
            })
        return results

    def _brute_force_retrieve(self, query_embedding: list[float], top_k: int) -> list[dict]:
        """Brute-force cosine similarity over all stored chunks."""
        chunks = self.db.get_all_chunks()
        if not chunks:
            return []

        scored = []
        for chunk in chunks:
            try:
                emb = json.loads(chunk.get("embedding", "[]"))
                if not emb:
                    continue
                score = cosine_similarity(query_embedding, emb)
                meta = json.loads(chunk.get("metadata", "{}")) if chunk.get("metadata") else {}
                scored.append({
                    "file_path": chunk["file_path"],
                    "content": chunk["content"],
                    "score": score,
                    "file_type": meta.get("type", "unknown"),
                    "summary": meta.get("summary", ""),
                    "functions": meta.get("functions", []),
                    "classes": meta.get("classes", []),
                })
            except Exception:
                continue

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
