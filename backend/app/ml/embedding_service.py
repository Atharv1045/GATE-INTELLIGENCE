"""
CPU-Friendly Lazy-Loaded Embedding & Similarity Service for GATE Intelligence.
- Uses `sentence-transformers/all-MiniLM-L6-v2` (384-d) when installed on the host.
- Falls back to a deterministic 384-dimensional normalized n-gram / mathematical token projection
  when running in offline/lightweight mode so embeddings are always versioned and never mixed.
- Computes TF-IDF cosine similarity and dense embedding cosine similarity without requiring a GPU.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple
import numpy as np

from app.core.config import settings


class LazyEmbeddingService:
    _instance: Optional["LazyEmbeddingService"] = None

    def __init__(self) -> None:
        self.model_name = settings.EMBEDDING_MODEL
        self.embedding_version = settings.EMBEDDING_VERSION
        self.dimension = settings.EMBEDDING_DIMENSION
        self._st_model = None
        self._st_attempted = False

    @classmethod
    def get_instance(cls) -> "LazyEmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_sentence_transformer_if_available(self) -> None:
        if self._st_attempted:
            return
        self._st_attempted = True
        try:
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(self.model_name, device="cpu")
        except Exception:
            self._st_model = None
            # Explicitly version deterministic CPU hash-projection embeddings separately
            if "hash384" not in self.embedding_version:
                self.embedding_version = f"{settings.EMBEDDING_VERSION}-cpu-hash384"

    @staticmethod
    def normalize_question_text(text: str, strip_numbers: bool = False) -> str:
        cleaned = text.lower().strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if strip_numbers:
            cleaned = re.sub(r"\b\d+(\.\d+)?\b", "<NUM>", cleaned)
        return cleaned

    @staticmethod
    def tokenize(text: str) -> List[str]:
        cleaned = re.sub(r"[^a-z0-9_+\-*/=<>^]", " ", text.lower())
        tokens = [t for t in cleaned.split() if len(t) > 1]
        return tokens

    def _deterministic_cpu_embed(self, text: str) -> List[float]:
        """
        Compute a deterministic 384-d unit vector using signed random projections over word unigrams,
        bigrams, and technical char-trigrams. Fast, zero-GPU, and preserves lexical & structural similarity.
        """
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = self.tokenize(text)
        if not tokens:
            return vec.tolist()

        features: List[Tuple[str, float]] = []
        for tok in tokens:
            features.append((f"u:{tok}", 1.0))
            if len(tok) >= 4:
                for i in range(len(tok) - 2):
                    features.append((f"c3:{tok[i:i+3]}", 0.35))
        for i in range(len(tokens) - 1):
            features.append((f"b:{tokens[i]}_{tokens[i+1]}", 1.25))

        for feat, weight in features:
            digest = hashlib.md5(feat.encode("utf-8")).digest()
            idx1 = int.from_bytes(digest[0:2], "little") % self.dimension
            idx2 = int.from_bytes(digest[2:4], "little") % self.dimension
            sign1 = 1.0 if (digest[4] & 1) == 0 else -1.0
            sign2 = 1.0 if (digest[5] & 1) == 0 else -1.0
            vec[idx1] += sign1 * weight
            vec[idx2] += sign2 * (weight * 0.5)

        norm = float(np.linalg.norm(vec))
        if norm > 1e-8:
            vec = vec / norm
        return [round(float(x), 6) for x in vec]

    def embed_text(self, text: str) -> Tuple[List[float], str, str]:
        """Returns (vector_384d, model_name, embedding_version)."""
        self._load_sentence_transformer_if_available()
        if self._st_model is not None:
            arr = self._st_model.encode(text, normalize_embeddings=True)
            return [round(float(x), 6) for x in arr.tolist()], self.model_name, self.embedding_version
        return self._deterministic_cpu_embed(text), "cpu-ngram-projection-384", self.embedding_version

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        a = np.asarray(vec_a, dtype=np.float32)
        b = np.asarray(vec_b, dtype=np.float32)
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom < 1e-9:
            return 0.0
        return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))

    @classmethod
    def tfidf_cosine(cls, text_a: str, text_b: str, idf_lookup: Optional[Dict[str, float]] = None) -> float:
        toks_a = cls.tokenize(text_a)
        toks_b = cls.tokenize(text_b)
        if not toks_a or not toks_b:
            return 0.0
        ca = Counter(toks_a)
        cb = Counter(toks_b)
        vocab = set(ca.keys()) | set(cb.keys())
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for term in vocab:
            idf = (idf_lookup or {}).get(term, 1.0)
            wa = (1.0 + math.log(ca[term])) * idf if ca[term] > 0 else 0.0
            wb = (1.0 + math.log(cb[term])) * idf if cb[term] > 0 else 0.0
            dot += wa * wb
            norm_a += wa * wa
            norm_b += wb * wb
        denom = math.sqrt(norm_a) * math.sqrt(norm_b)
        return float(dot / denom) if denom > 1e-9 else 0.0
