"""Local sentence-transformer embeddings with SQLite cache (per claim hash)."""

from __future__ import annotations

import hashlib
import sqlite3
from functools import lru_cache
from typing import Any

import numpy as np

from email_digest.cache import get_embedding_vector, put_embedding_vector

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def claim_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _load_model(model_name: str = DEFAULT_MODEL_NAME) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_claim_texts(
    texts: list[str],
    *,
    conn: sqlite3.Connection,
    model_name: str = DEFAULT_MODEL_NAME,
) -> np.ndarray:
    """Return ``(n, dim)`` float32 matrix (L2-normalized rows), one row per *texts* order."""
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    hashes = [claim_hash(t) for t in texts]
    pending_i: list[int] = []
    pending_h: list[str] = []
    pending_t: list[str] = []
    staged: list[tuple[int, np.ndarray]] = []

    for i, (text, h) in enumerate(zip(texts, hashes, strict=True)):
        cached = get_embedding_vector(conn, h)
        if cached is not None:
            staged.append((i, np.asarray(cached, dtype=np.float32)))
        else:
            pending_i.append(i)
            pending_h.append(h)
            pending_t.append(text)

    if pending_t:
        model = _load_model(model_name)
        encoded = model.encode(
            pending_t,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        batch = np.asarray(encoded, dtype=np.float32)
        for k, h in enumerate(pending_h):
            vec = batch[k]
            put_embedding_vector(conn, h, vec)
            staged.append((pending_i[k], vec))

    staged.sort(key=lambda x: x[0])
    return np.stack([v for _, v in staged], axis=0)
