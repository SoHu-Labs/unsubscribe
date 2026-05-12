"""litellm-backed completion with provider aliases."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import litellm

from email_digest.cache import connect, insert_llm_call
from email_digest.paths import default_cache_db_path

MODEL_ALIASES: dict[str, str] = {
    "fast": "deepseek/deepseek-v4-flash",
    "smart": "deepseek/deepseek-v4-pro",
    # LM Studio: model ids come from env (LM Studio Local Server UI strings).
    "local": "openai/local-model",
    "local_smart": "openai/local-model",
}


def _resolve_model(alias: str) -> str:
    if alias == "local":
        return os.environ.get("LM_STUDIO_MODEL", MODEL_ALIASES["local"])
    if alias == "local_smart":
        return os.environ.get(
            "LM_STUDIO_MODEL_SMART",
            os.environ.get("LM_STUDIO_MODEL", MODEL_ALIASES["local_smart"]),
        )
    return MODEL_ALIASES.get(alias, alias)


def _opencode_auth_json_path() -> Path:
    return Path.home() / ".local" / "share" / "opencode" / "auth.json"


def read_deepseek_key_from_opencode_auth_files() -> str | None:
    """Return DeepSeek API key from OpenCode's auth.json if present; else None."""
    path = _opencode_auth_json_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    block = data.get("deepseek")
    if not isinstance(block, dict):
        return None
    key = block.get("key")
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def _ensure_deepseek_env_from_opencode() -> None:
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return
    key = read_deepseek_key_from_opencode_auth_files()
    if key:
        os.environ["DEEPSEEK_API_KEY"] = key


def _require_deepseek_key_if_needed(model: str) -> None:
    if "deepseek" not in model.lower():
        return
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return
    raise ValueError(
        "DEEPSEEK_API_KEY is not set (or is empty). Topic YAML uses DeepSeek for "
        "aliases like 'fast' / 'smart'. Export a valid key, or add one under "
        "`deepseek.key` in OpenCode auth at ~/.local/share/opencode/auth.json. "
        "Copying `.env.example` to `.env` does not load into Python automatically "
        "unless you source it or use direnv."
    )


def complete(
    messages: list[dict[str, Any]],
    alias: str = "smart",
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    model = _resolve_model(alias)
    _ensure_deepseek_env_from_opencode()
    _require_deepseek_key_if_needed(model)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    if alias in ("local", "local_smart"):
        kwargs["api_base"] = os.environ.get(
            "LM_STUDIO_BASE_URL", "http://localhost:1234/v1"
        ).rstrip("/")
        kwargs["api_key"] = os.environ.get("LM_STUDIO_API_KEY", "lm-studio")

    resp = litellm.completion(**kwargs)
    choice = resp.choices[0].message
    content = getattr(choice, "content", None) or ""
    _log_llm_call(alias=alias, model=model, response=resp)
    return str(content)


def _log_llm_call(*, alias: str, model: str, response: Any) -> None:
    try:
        cost_usd: float | None
        try:
            cost_usd = float(litellm.completion_cost(completion_response=response))
        except Exception:
            cost_usd = None
        usage = getattr(response, "usage", None)
        inp = getattr(usage, "prompt_tokens", None) if usage is not None else None
        out = getattr(usage, "completion_tokens", None) if usage is not None else None
        if usage is not None and inp is None and hasattr(usage, "model_dump"):
            ud = usage.model_dump()
            if isinstance(ud, dict):
                inp = ud.get("prompt_tokens")
                out = ud.get("completion_tokens")
        db_path = default_cache_db_path()
        conn = connect(db_path)
        try:
            insert_llm_call(
                conn,
                alias=alias,
                model=model,
                input_tokens=inp,
                output_tokens=out,
                cost_usd=cost_usd,
            )
        finally:
            conn.close()
    except Exception as e:
        print(f"(digest: could not log LLM call to SQLite: {e})", file=sys.stderr)
