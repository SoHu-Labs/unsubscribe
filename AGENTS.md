# email-digest — project guide for the agent

## Setup

```bash
mamba run -n email-digest python -m email_digest digest <command>
```

GOOGLE_OAUTH_TOKEN must point to a valid Gmail API user token at `~/.google/oauth_token.json` (scopes: gmail.readonly + gmail.send). DeepSeek models via DEEPSEEK_API_KEY or auth.json. Cheap alias uses OpenCode Go API key from auth.json.

## Commands

| Task | Command |
|------|---------|
| Dry-run health digest | `mamba run -n email-digest python -m email_digest digest run health --dry-run` |
| Dry-run all topics | `mamba run -n email-digest python -m email_digest digest run --all --dry-run` |
| List candidates | `mamba run -n email-digest python -m email_digest digest candidates <topic> --max-results 10` |
| Walkthrough (interactive) | `mamba run -n email-digest python -m email_digest digest walkthrough <topic> [--body]` |
| Full run (no dry-run) | `mamba run -n email-digest python -m email_digest digest run <topic>` |
| Cost report | `mamba run -n email-digest python -m email_digest digest cost --json` |
| Validate topics | `mamba run -n email-digest python -m email_digest digest topics --strict` |
| Run all tests | `mamba run -n email-digest python -m pytest tests/ -q` |

## Topic YAML

Topics live in `topics/<stem>.yaml`. Each has `senders` (From addresses), optional `keywords` (subject/body search terms), and `extract_model` / `synthesize_model` aliases.

Available model aliases: `fast` (DeepSeek V4 Flash), `smart` (DeepSeek V4 Pro), `local` (Qwen3.5-2B direct MLX), `local_smart` (Qwen3.5-4B direct MLX), `cheap` (MiniMax M2.5 via OpenCode Go).

## Model routing

- `fast`/`smart` → DeepSeek API (`DEEPSEEK_API_KEY` or auth.json `deepseek.key`)
- `local`/`local_smart` → Direct MLX via `mlx_lm` (models loaded from `~/.lmstudio/models/`, mirrored from `local-chat/src/llm.py` `MODEL_VARIANTS`). No env vars.
- `cheap` → OpenCode Go API (`https://opencode.ai/zen/go/v1`, key from auth.json or `CHEAP_API_KEY`)
