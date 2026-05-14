# Local LLM — digest operators

Digest topic YAML may use aliases `local` and `local_smart` for on-device LLM inference. These use **direct MLX** (`mlx_lm`), not LM Studio's HTTP server. No env vars needed.

## Model variants

Model paths are hardcoded in `src/email_digest/llm.py` (`MLX_MODEL_VARIANTS`, mirrors `local-chat/src/llm.py`):

| Key | Model | Path on disk |
|-----|-------|-------------|
| `qwen3` | Qwen3-4B-Instruct | `~/.lmstudio/models/lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit` |
| `0.8b` | Qwen3.5-0.8B | `~/.lmstudio/models/mlx-community/Qwen3.5-0.8B-MLX-4bit` |
| `2b` | Qwen3.5-2B | `~/.lmstudio/models/mlx-community/Qwen3.5-2B-MLX-4bit` |
| `4b` | Qwen3.5-4B | `~/.lmstudio/models/mlx-community/Qwen3.5-4B-MLX-4bit` |

## Alias mapping

| Alias | Variant | Model |
|-------|---------|-------|
| `local` | `"2b"` | Qwen3.5-2B (default, matches local-chat) |
| `local_smart` | `"4b"` | Qwen3.5-4B |

## Diagnostics

From Python (after `pip install -e ".[dev]"`):

```python
from email_digest.llm import resolve_model_alias
print(resolve_model_alias("local"), resolve_model_alias("local_smart"))
```

LLM usage and token counts for all models are summarized by `python -m email_digest digest cost` (SQLite log). Local calls record `cost_usd=0`.
