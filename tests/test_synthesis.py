"""Digest synthesis LLM wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from email_digest.config import load_topic_config
from email_digest.synthesis import synthesize_digest

_TOPICS = Path(__file__).resolve().parent.parent / "topics"


def test_synthesize_digest_parses_json() -> None:
    cfg = load_topic_config(_TOPICS / "ai.yaml")
    bundle = {
        "topic": "ai",
        "trending": [],
        "messages": [
            {
                "id": "m1",
                "rfc_message_id": "<x@y.com>",
                "from": "A",
                "subject": "S",
                "date": "d",
                "extraction": {"key_claims": []},
            }
        ],
    }
    fake = json.dumps({"trending": [], "highlights": []})
    with patch("email_digest.synthesis.llm_complete", return_value=fake):
        out = synthesize_digest(cfg, bundle)
    assert out == {"trending": [], "highlights": []}
