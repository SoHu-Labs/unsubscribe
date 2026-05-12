"""Trending detection via HDBSCAN on normalized embeddings."""

from __future__ import annotations

from typing import Any

import hdbscan
import numpy as np


def cluster_labels(
    embeddings: np.ndarray,
    *,
    min_cluster_size: int,
    algorithm: str = "hdbscan",
) -> np.ndarray:
    """Return integer cluster labels (``-1`` = noise)."""
    if embeddings.size == 0:
        return np.array([], dtype=np.int32)
    if algorithm != "hdbscan":
        raise ValueError(f"Unsupported clustering algorithm: {algorithm!r}")
    X = np.asarray(embeddings, dtype=np.float64)
    if X.shape[0] == 1:
        return np.array([-1], dtype=np.int32)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    Xn = X / norms
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=max(2, min_cluster_size),
        metric="euclidean",
    )
    return clusterer.fit_predict(Xn).astype(np.int32)


def filter_clusters_by_cohesion(
    embeddings: np.ndarray,
    labels: np.ndarray,
    *,
    min_mean_cosine: float,
) -> np.ndarray:
    """Drop clusters whose mean pairwise cosine similarity falls below *min_mean_cosine*."""
    if embeddings.size == 0:
        return labels
    X = np.asarray(embeddings, dtype=np.float64)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    Xn = X / norms
    out = np.asarray(labels, dtype=np.int32).copy()
    for lab in np.unique(out):
        if int(lab) < 0:
            continue
        idx = np.where(out == lab)[0]
        if idx.size < 2:
            out[idx] = -1
            continue
        sub = Xn[idx]
        sim = sub @ sub.T
        tri = np.triu_indices(int(idx.size), k=1)
        mean_cos = float(np.mean(sim[tri]))
        if mean_cos < min_mean_cosine:
            out[idx] = -1
    return out


def trending_clusters(
    claims: list[dict[str, Any]],
    labels: np.ndarray,
) -> list[dict[str, Any]]:
    """Group claims by non-negative cluster id."""
    from collections import defaultdict

    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for claim, lab in zip(claims, labels, strict=True):
        li = int(lab)
        if li < 0:
            continue
        buckets[li].append(claim)
    return [
        {"cluster_id": cid, "claims": members}
        for cid, members in sorted(buckets.items())
    ]
