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
    assert "briefing@machine-learning-weekly.example.com" in cfg.senders
    assert "digest@voice-ai-roundup.example.com" in cfg.senders
    assert cfg.window_days == 7
    assert cfg.extract_model == "fast"
    assert cfg.synthesize_model == "smart"
    assert "Virtual Friend" in cfg.persona_prompt
    assert cfg.trending_min_cluster_size == 2
    assert cfg.output_template == "digest_html"


def test_topic_config_frozen() -> None:
    cfg = load_topic_config(_TOPICS / "health.yaml")
    with pytest.raises(FrozenInstanceError):
        cfg.name = "x"  # type: ignore[misc]


def test_repo_topic_yaml_senders_contain_no_todo_prefix() -> None:
    """R6: shipped topics must not ship ``TODO-`` sender placeholders (regression guard)."""
    for path in sorted(_TOPICS.glob("*.yaml")):
        cfg = load_topic_config(path)
        for s in cfg.senders:
            assert "todo-" not in s.lower(), f"{path.name}: sender {s!r}"


def test_load_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_topic_config(_TOPICS / "nonexistent.yaml")
