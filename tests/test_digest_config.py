"""Topic YAML → TopicConfig."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from email_digest.config import load_topic_config

_TOPICS = Path(__file__).resolve().parent.parent / "topics"


def test_load_ai_topic() -> None:
    cfg = load_topic_config(_TOPICS / "ai.yaml")
    assert cfg.name == "ai"
    assert "TODO-your-ai-newsletter@example.com" in cfg.senders
    assert cfg.window_days == 7
    assert cfg.extract_model == "fast"
    assert cfg.synthesize_model == "smart"
    assert "Virtual Friend" in cfg.persona_prompt
    assert cfg.trending_min_cluster_size == 2
    assert cfg.output_template == "digest_html"


def test_topic_config_frozen() -> None:
    cfg = load_topic_config(_TOPICS / "health_psy.yaml")
    with pytest.raises(FrozenInstanceError):
        cfg.name = "x"  # type: ignore[misc]


def test_load_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_topic_config(_TOPICS / "nonexistent.yaml")
