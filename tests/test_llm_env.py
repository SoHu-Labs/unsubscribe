"""LLM env preflight (DeepSeek key) and OpenCode auth.json fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from email_digest.llm import complete, read_deepseek_key_from_opencode_auth_files


def test_complete_raises_clear_error_when_deepseek_key_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        complete([{"role": "user", "content": "hi"}], alias="fast")


def test_read_deepseek_from_opencode_auth_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    auth = tmp_path / ".local" / "share" / "opencode"
    auth.mkdir(parents=True)
    (auth / "auth.json").write_text(
        json.dumps({"deepseek": {"type": "api", "key": "sk-from-opencode-json"}}),
        encoding="utf-8",
    )
    assert read_deepseek_key_from_opencode_auth_files() == "sk-from-opencode-json"


def test_complete_uses_opencode_when_env_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    auth = tmp_path / ".local" / "share" / "opencode"
    auth.mkdir(parents=True)
    (auth / "auth.json").write_text(
        json.dumps({"deepseek": {"type": "api", "key": "sk-opencode-for-complete"}}),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    class _Msg:
        content = "ok"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]
        usage = None

    def fake_completion(**kwargs: Any) -> _Resp:
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("email_digest.llm.litellm.completion", fake_completion)

    out = complete([{"role": "user", "content": "hi"}], alias="fast")
    assert out == "ok"
    assert "model" in captured
