"""litellm-backed completion with provider aliases + MLX local models."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import litellm

from email_digest.cache import connect, insert_llm_call
from email_digest.paths import default_cache_db_path

_MODELS = Path.home() / ".lmstudio" / "models"

MLX_MODEL_VARIANTS: dict[str, str] = {
    "qwen3": str(_MODELS / "lmstudio-community" / "Qwen3-4B-Instruct-2507-MLX-4bit"),
    "0.8b":  str(_MODELS / "mlx-community" / "Qwen3.5-0.8B-MLX-4bit"),
    "2b":    str(_MODELS / "mlx-community" / "Qwen3.5-2B-MLX-4bit"),
    "4b":    str(_MODELS / "mlx-community" / "Qwen3.5-4B-MLX-4bit"),
}

# Qwen3.5 variants are multimodal weight files; load with strict=False to use
# only the language model portion (vision tower weights are silently skipped).
_MLX_VLM_KEYS = {"0.8b", "2b", "4b"}

_MLX_DEFAULT = "qwen3"

MODEL_ALIASES: dict[str, str] = {
    "fast": "deepseek/deepseek-v4-flash",
    "smart": "deepseek/deepseek-v4-pro",
    "local": _MLX_DEFAULT,
    "local_smart": "4b",
    # Cheap / MiniMax via OpenCode Go API (OpenAI-compatible endpoint).
    # Default model minimax-m2.5 is included in the Go subscription ($10/mo).
    # Endpoint: https://opencode.ai/zen/go/v1 (NOT the Zen endpoint).
    "cheap": "openai/minimax-m2.5",
}

# Aliases that route through the OpenCode Go API (OpenAI-compatible endpoint).
# fast / smart default to Go API with a user-confirmed fallback to direct DeepSeek.
_GO_API_ALIASES = frozenset({"fast", "smart", "cheap"})

# Lazy-loaded MLX models (singleton per variant, mirrors local-chat MlxLlm).
_mlx_models: dict[str, tuple[Any, Any]] = {}


def _get_mlx_model(variant: str) -> tuple[Any, Any]:
    """Lazy-load and cache (model, tokenizer) tuple per variant."""
    if variant in _mlx_models:
        return _mlx_models[variant]
    model_path = Path(MLX_MODEL_VARIANTS[variant])
    use_vlm = variant in _MLX_VLM_KEYS
    from mlx_lm.utils import load_model, load_tokenizer

    if use_vlm:
        model, _ = load_model(model_path, strict=False)
    else:
        model, _ = load_model(model_path)
    tokenizer = load_tokenizer(model_path)
    entry = (model, tokenizer)
    _mlx_models[variant] = entry
    return entry


def _resolve_model(alias: str) -> str:
    if alias in ("local", "local_smart"):
        return MLX_MODEL_VARIANTS[MODEL_ALIASES[alias]]
    if alias == "cheap":
        return os.environ.get("CHEAP_MODEL", MODEL_ALIASES["cheap"])
    return MODEL_ALIASES.get(alias, alias)


def resolve_model_alias(alias: str) -> str:
    """Return the concrete litellm model id (or MLX path) for a digest YAML alias."""
    return _resolve_model(alias)


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


def _read_opencode_zen_auth_key() -> str | None:
    """Return Zen API key from OpenCode auth.json (try opencode, zen, opencode-zen, opencode-go)."""
    path = _opencode_auth_json_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    for block_name in ("opencode", "zen", "opencode-zen", "opencode-go"):
        block = data.get(block_name)
        if isinstance(block, dict):
            key = block.get("key") or block.get("apiKey")
            if isinstance(key, str) and key.strip():
                return key.strip()
    return None


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


def _mlx_complete(
    messages: list[dict[str, Any]],
    variant: str,
    *,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> tuple[str, int, int]:
    """Generate using local MLX model. Returns (text, prompt_tokens, gen_tokens)."""
    model, tokenizer = _get_mlx_model(variant)
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    msgs = list(messages)
    if json_mode:
        if msgs and msgs[0].get("role") == "system":
            msgs[0] = dict(msgs[0])
            msgs[0]["content"] = (
                str(msgs[0]["content"])
                + "\n\nRespond with valid JSON only, no markdown fences."
            )
        else:
            msgs.insert(
                0,
                {
                    "role": "system",
                    "content": "Respond with valid JSON only, no markdown fences.",
                },
            )

    prompt = tokenizer.apply_chat_template(
        msgs,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    prompt_tokens = len(tokenizer.encode(prompt))
    sampler = make_sampler(temp=temperature, min_p=0.05, top_k=50)
    response = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        sampler=sampler,
    )
    response = response.strip()
    gen_tokens = len(tokenizer.encode(response))
    return response, prompt_tokens, gen_tokens


def _log_mlx_call(
    *, alias: str, model: str, input_tokens: int, output_tokens: int
) -> None:
    try:
        db_path = default_cache_db_path()
        conn = connect(db_path)
        try:
            insert_llm_call(
                conn,
                alias=alias,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=0.0,
            )
        finally:
            conn.close()
    except Exception as e:
        print(f"(digest: could not log MLX call to SQLite: {e})", file=sys.stderr)


def _complete_via_mlx(
    messages: list[dict[str, Any]],
    alias: str,
    *,
    max_tokens: int,
    temperature: float,
    json_mode: bool,
) -> str:
    """Run a local MLX model and return its text content."""
    assert alias in ("local", "local_smart"), f"not an MLX alias: {alias!r}"
    variant = MODEL_ALIASES[alias]
    model_path = MLX_MODEL_VARIANTS[variant]
    content, prompt_tokens, gen_tokens = _mlx_complete(
        messages,
        variant=variant,
        max_tokens=max_tokens,
        temperature=temperature,
        json_mode=json_mode,
    )
    _log_mlx_call(
        alias=alias,
        model=model_path,
        input_tokens=prompt_tokens,
        output_tokens=gen_tokens,
    )
    return content


def complete(
    messages: list[dict[str, Any]],
    alias: str = "smart",
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    """Completion via litellm with Go API routing for fast/smart/cheap and MLX local."""
    # --- MLX local models -------------------------------------------------------
    if alias in ("local", "local_smart"):
        return _complete_via_mlx(
            messages, alias,
            max_tokens=max_tokens, temperature=temperature, json_mode=json_mode,
        )

    model = _resolve_model(alias)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    # --- OpenCode Go API path (fast, smart, cheap) -------------------------------
    if alias in _GO_API_ALIASES:
        go_key = os.environ.get("CHEAP_API_KEY", "") or _read_opencode_zen_auth_key() or ""

        if not go_key and alias in ("fast", "smart"):
            # No Go API key — skip Go entirely, go direct to DeepSeek.
            print(
                "Go API key not set, using direct DeepSeek API.",
                file=sys.stderr,
                flush=True,
            )
            _ensure_deepseek_env_from_opencode()
            _require_deepseek_key_if_needed(model)
            kwargs["api_key"] = os.environ.get("DEEPSEEK_API_KEY", "")
            resp = litellm.completion(**kwargs)
        else:
            # Try the Go API (fast/smart/cheap).
            kwargs["api_base"] = os.environ.get(
                "GO_API_BASE", "https://opencode.ai/zen/go/v1"
            ).rstrip("/")
            if not go_key:
                print(
                    "Go API key not set. Connect Go with `opencode /connect`, "
                    "or export CHEAP_API_KEY from https://opencode.ai/auth.",
                    file=sys.stderr,
                    flush=True,
                )
            kwargs["api_key"] = go_key
            try:
                resp = litellm.completion(**kwargs)
            except Exception as exc:
                if alias not in ("fast", "smart", "cheap"):
                    raise  # unknown alias, no fallback

                if alias == "cheap":
                    # cheap → offer local model fallback (default local_smart)
                    print(
                        f"\nGo API request failed for cheap ({model}): {exc}",
                        file=sys.stderr,
                    )
                    if sys.stdin.isatty():
                        answer = input(
                            "Fall back to local model? [local_smart/local/N]: "
                        ).strip().lower()
                    else:
                        print(
                            "Non-interactive session — defaulting to local_smart.",
                            file=sys.stderr,
                        )
                        answer = ""
                    if answer == "local":
                        fallback_alias = "local"
                    elif answer in ("local_smart", ""):
                        fallback_alias = "local_smart"
                    else:
                        print("Aborting.", file=sys.stderr)
                        raise
                    print(
                        f"Falling back to {fallback_alias} ("
                        f"{MLX_MODEL_VARIANTS[MODEL_ALIASES[fallback_alias]]}).",
                        file=sys.stderr,
                    )
                    return _complete_via_mlx(
                        messages, fallback_alias,
                        max_tokens=max_tokens, temperature=temperature,
                        json_mode=json_mode,
                    )

                # fast / smart: ask user before falling back to direct DeepSeek
                print(
                    f"\nGo API request failed for {alias} ({model}): {exc}",
                    file=sys.stderr,
                )
                if sys.stdin.isatty():
                    answer = input(
                        "Fall back to direct DeepSeek API? [y/N]: "
                    ).strip().lower()
                else:
                    print(
                        "Non-interactive session — skipping fallback prompt.",
                        file=sys.stderr,
                    )
                    answer = ""
                if answer not in ("y", "yes"):
                    print("Aborting.", file=sys.stderr)
                    raise
                print("Falling back to direct DeepSeek API.", file=sys.stderr)
                # Strip Go API params and switch to direct DeepSeek
                kwargs.pop("api_base", None)
                _ensure_deepseek_env_from_opencode()
                _require_deepseek_key_if_needed(model)
                kwargs["api_key"] = os.environ.get("DEEPSEEK_API_KEY", "")
                resp = litellm.completion(**kwargs)
    else:
        # --- Direct provider path (DeepSeek or pass-through alias) ---------------
        _ensure_deepseek_env_from_opencode()
        _require_deepseek_key_if_needed(model)
        resp = litellm.completion(**kwargs)

    choice = resp.choices[0].message
    content = getattr(choice, "content", None) or ""
    _log_litellm_call(alias=alias, model=model, response=resp)
    return str(content)


def _log_litellm_call(*, alias: str, model: str, response: Any) -> None:
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
