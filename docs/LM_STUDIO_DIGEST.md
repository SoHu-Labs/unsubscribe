# LM Studio — digest operators

Digest topic YAML may use aliases `local` and `local_smart` for LM Studio’s OpenAI-compatible Local Server. Those aliases resolve to litellm model ids read from the environment (see `resolve_model_alias` in `src/email_digest/llm.py`).

## Environment variables

| Variable | Used by alias | Effect |
|----------|----------------|--------|
| `LM_STUDIO_MODEL` | `local` | Overrides the default `openai/local-model` placeholder. |
| `LM_STUDIO_MODEL_SMART` | `local_smart` | Overrides the smart-local default; if unset, falls back to `LM_STUDIO_MODEL`, then to the same default as `local`. |

Set these to the **exact model id string** shown in LM Studio’s Local Server UI (not necessarily the on-disk folder name under `~/.lmstudio/models/`).

## Recommended presets (on-disk reference)

These are **targets** for local development, not values baked into code:

1. **Qwen3.5 4B MLX** — on-disk `mlx-community/Qwen3.5-4B-MLX-4bit` — good default for `local` / extraction-style workloads.
2. **Qwen3-4B-Instruct** — on-disk `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit` — good default for `local_smart` / heavier local synthesis.

UI labels can differ from folder names: always copy the id from LM Studio’s server panel into `LM_STUDIO_MODEL` / `LM_STUDIO_MODEL_SMART`.

## Base URL

`LM_STUDIO_BASE_URL` (e.g. `http://localhost:1234/v1`) is documented in the root `README.md` with other credentials.

## Diagnostics

From Python (after `pip install -e ".[dev]"`):

```python
from email_digest.llm import resolve_model_alias
print(resolve_model_alias("local"), resolve_model_alias("local_smart"))
```

LLM usage and costs when using cloud models are summarized by `python -m email_digest digest cost` (SQLite log).
