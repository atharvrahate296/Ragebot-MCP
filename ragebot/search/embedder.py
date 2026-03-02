"""
Embedder - Creates vector embeddings for text chunks.
Supports sentence-transformers and OpenAI embeddings.
"""
from __future__ import annotations

import json
import pickle
import hashlib
from pathlib import Path
from typing import List, Optional


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_dir: Optional[Path] = None):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None
        self._tried_import: bool = False
        self._dimension: Optional[int] = None

        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[float]] = {}
        self._load_cache()

    @property
    def model(self):
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        cache_key = hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        embedding = self._compute_embedding(text)
        self._cache[cache_key] = embedding
        self._save_cache()
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts, using cache where possible."""
        results = []
        to_compute = []
        to_compute_indices = []

        for i, text in enumerate(texts):
            cache_key = hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()
            if cache_key in self._cache:
                results.append((i, self._cache[cache_key]))
            else:
                to_compute.append(text)
                to_compute_indices.append(i)

        if to_compute:
            computed = self._compute_batch(to_compute)
            for i, (text_idx, embedding) in enumerate(zip(to_compute_indices, computed)):
                cache_key = hashlib.md5(f"{self.model_name}:{to_compute[i]}".encode()).hexdigest()
                self._cache[cache_key] = embedding
                results.append((text_idx, embedding))
            self._save_cache()

        # Sort back to original order
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]

    def dimension(self) -> int:
        if self._dimension is None:
            sample = self.embed("test")
            self._dimension = len(sample)
        return self._dimension

    # ── Private ───────────────────────────────────────────────────────────────

    def _load_model(self):
        """Load the embedding model (called once via the model property)."""
        if self._tried_import:
            return self._model
        self._tried_import = True
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            return self._model
        except (ImportError, Exception):
            self._model = None
            return None

    def _compute_embedding(self, text: str) -> list[float]:
        if self.model is None:
            return self._fallback_embedding(text)
        try:
            from sentence_transformers import SentenceTransformer
            model = self.model
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception:
            return self._fallback_embedding(text)

    def _compute_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
            model = self.model
            embeddings = model.encode(texts, convert_to_numpy=True, batch_size=32)
            return [e.tolist() for e in embeddings]
        except Exception:
            return [self._fallback_embedding(t) for t in texts]

    def _fallback_embedding(self, text: str, dim: int = 128) -> list[float]:
        """Simple hash-based fallback when sentence-transformers is unavailable."""
        import math
        words = text.lower().split()
        embedding = [0.0] * dim
        for i, word in enumerate(words[:dim]):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            embedding[h % dim] += 1.0 / (i + 1)
        # Normalize
        magnitude = math.sqrt(sum(x * x for x in embedding)) or 1.0
        return [x / magnitude for x in embedding]

    def _load_cache(self):
        if not self.cache_dir:
            return
        cache_file = self.cache_dir / "embedding_cache.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    self._cache = pickle.load(f)
            except Exception:
                self._cache = {}

    def _save_cache(self):
        if not self.cache_dir:
            return
        cache_file = self.cache_dir / "embedding_cache.pkl"
        try:
            with open(cache_file, "wb") as f:
                pickle.dump(self._cache, f)
        except Exception:
            pass
