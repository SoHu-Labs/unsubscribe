"""Embedding cache + batching (``sentence_transformers`` mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from email_digest.cache import connect, get_embedding_vector
from email_digest.embed import claim_hash, embed_claim_texts


def test_claim_hash_stable() -> None:
    assert claim_hash("  hi  ") == claim_hash("hi")


def test_embed_claim_texts_batch_and_cache(tmp_path: Path) -> None:
    db = tmp_path / "e.sqlite"
    conn = connect(db)
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
    )
    with patch("email_digest.embed._load_model", return_value=mock_model):
        out = embed_claim_texts(["alpha", "beta"], conn=conn)
    assert out.shape == (2, 3)
    mock_model.encode.assert_called_once()
    h0 = claim_hash("alpha")
    assert get_embedding_vector(conn, h0) is not None
    conn.close()

    conn2 = connect(db)
    mock_model.encode.reset_mock()
    with patch("email_digest.embed._load_model", return_value=mock_model):
        out2 = embed_claim_texts(["alpha", "gamma"], conn=conn2)
    assert out2.shape == (2, 3)
    # "alpha" hits cache; only "gamma" should be encoded in a batch of size 1
    assert mock_model.encode.call_count == 1
    conn2.close()
