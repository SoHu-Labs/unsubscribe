"""``resolve_model_alias`` — operator-visible LM Studio env resolution (slice C)."""

from __future__ import annotations

import pytest

from email_digest.llm import MODEL_ALIASES, resolve_model_alias


def test_resolve_fast_unchanged() -> None:
    assert resolve_model_alias("fast") == MODEL_ALIASES["fast"]
    assert resolve_model_alias("smart") == MODEL_ALIASES["smart"]


def test_resolve_local_reads_lm_studio_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LM_STUDIO_MODEL", "openai/custom-local")
    assert resolve_model_alias("local") == "openai/custom-local"


def test_resolve_local_smart_prefers_lm_studio_model_smart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LM_STUDIO_MODEL", "openai/base")
    monkeypatch.setenv("LM_STUDIO_MODEL_SMART", "openai/smart-only")
    assert resolve_model_alias("local_smart") == "openai/smart-only"


def test_resolve_local_smart_falls_back_to_lm_studio_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LM_STUDIO_MODEL_SMART", raising=False)
    monkeypatch.setenv("LM_STUDIO_MODEL", "openai/base")
    assert resolve_model_alias("local_smart") == "openai/base"


def test_resolve_local_smart_falls_back_to_default_when_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LM_STUDIO_MODEL_SMART", raising=False)
    monkeypatch.delenv("LM_STUDIO_MODEL", raising=False)
    assert resolve_model_alias("local_smart") == MODEL_ALIASES["local_smart"]
