"""Unit tests for :mod:`email_digest.cluster` (no sentence-transformers)."""

from __future__ import annotations

import numpy as np

from email_digest.cluster import (
    cluster_labels,
    filter_clusters_by_cohesion,
    trending_clusters,
)


def test_cluster_labels_two_blobs() -> None:
    """HDBSCAN should return one label per row without raising."""
    rng = np.random.default_rng(0)
    a = rng.normal(size=(8, 3)) + np.array([0.0, 0.0, 0.0])
    b = rng.normal(size=(8, 3)) + np.array([20.0, 0.0, 0.0])
    x = np.vstack([a, b])
    labs = cluster_labels(x, min_cluster_size=3)
    assert labs.shape == (16,)


def test_filter_clusters_by_cohesion_drops_orthogonal() -> None:
    x = np.array(
        [
            [1.0, 0.0],
            [1.0, 0.01],
            [0.0, 1.0],
            [0.0, 1.01],
        ],
        dtype=np.float64,
    )
    labels = np.array([0, 0, 0, 0], dtype=np.int32)
    out = filter_clusters_by_cohesion(
        x, labels, min_mean_cosine=0.99
    )  # intra-cluster must be very tight
    assert (out == -1).all()


def test_trending_clusters_groups() -> None:
    claims = [
        {"message_id": "a", "claim_index": 0, "text": "t1"},
        {"message_id": "b", "claim_index": 0, "text": "t2"},
    ]
    labs = np.array([7, 7], dtype=np.int32)
    out = trending_clusters(claims, labs)
    assert len(out) == 1
    assert out[0]["cluster_id"] == 7
    assert len(out[0]["claims"]) == 2
