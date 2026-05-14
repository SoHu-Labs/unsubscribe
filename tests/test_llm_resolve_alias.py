"""``resolve_model_alias`` — returns MLX paths for local, litellm ids otherwise."""

from __future__ import annotations

from pathlib import Path

import pytest

from email_digest.llm import (
    MLX_MODEL_VARIANTS,
    MODEL_ALIASES,
    _read_opencode_zen_auth_key,
    resolve_model_alias,
)


def test_resolve_fast_unchanged() -> None:
    assert resolve_model_alias("fast") == MODEL_ALIASES["fast"]
    assert resolve_model_alias("smart") == MODEL_ALIASES["smart"]


def test_resolve_local_returns_mlx_path() -> None:
    assert resolve_model_alias("local") == MLX_MODEL_VARIANTS[MODEL_ALIASES["local"]]


def test_resolve_local_smart_returns_mlx_path() -> None:
    assert resolve_model_alias("local_smart") == MLX_MODEL_VARIANTS[
        MODEL_ALIASES["local_smart"]
    ]


def test_resolve_cheap_default() -> None:
    assert resolve_model_alias("cheap") == MODEL_ALIASES["cheap"]


def test_resolve_cheap_reads_cheap_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHEAP_MODEL", "openai/minimax-m2.7")
    assert resolve_model_alias("cheap") == "openai/minimax-m2.7"


def test_resolve_cheap_falls_back_to_default_when_no_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CHEAP_MODEL", raising=False)
    assert resolve_model_alias("cheap") == MODEL_ALIASES["cheap"]


def test_read_opencode_zen_auth_key_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "nonexistent.json"
    monkeypatch.setattr("email_digest.llm._opencode_auth_json_path", lambda: p)
    assert _read_opencode_zen_auth_key() is None


def test_read_opencode_zen_auth_key_no_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "auth.json"
    p.write_text('{"deepseek": {"key": "sk-xxx"}}', encoding="utf-8")
    monkeypatch.setattr("email_digest.llm._opencode_auth_json_path", lambda: p)
    assert _read_opencode_zen_auth_key() is None


def test_read_opencode_zen_auth_key_opencode_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "auth.json"
    p.write_text('{"opencode": {"key": "zen-key-123"}}', encoding="utf-8")
    monkeypatch.setattr("email_digest.llm._opencode_auth_json_path", lambda: p)
    assert _read_opencode_zen_auth_key() == "zen-key-123"


def test_read_opencode_zen_auth_key_zen_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "auth.json"
    p.write_text('{"zen": {"key": "zen-key-456"}}', encoding="utf-8")
    monkeypatch.setattr("email_digest.llm._opencode_auth_json_path", lambda: p)
    assert _read_opencode_zen_auth_key() == "zen-key-456"


def test_read_opencode_zen_auth_key_uses_apiKey_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "auth.json"
    p.write_text('{"opencode-zen": {"apiKey": "zen-from-apikey"}}', encoding="utf-8")
    monkeypatch.setattr("email_digest.llm._opencode_auth_json_path", lambda: p)
    assert _read_opencode_zen_auth_key() == "zen-from-apikey"


def test_read_opencode_zen_auth_key_opencode_go_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "auth.json"
    p.write_text('{"opencode-go": {"key": "sk-go-key-789"}}', encoding="utf-8")
    monkeypatch.setattr("email_digest.llm._opencode_auth_json_path", lambda: p)
    assert _read_opencode_zen_auth_key() == "sk-go-key-789"
