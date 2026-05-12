# email-digest

Two email tools sharing one Gmail API backend:

- **unsubscribe** — automate unsubscribing from newsletters
- **digest** — topic-oriented email summaries with LLM synthesis and trending detection

## Setup

```bash
mamba env create -f environment.yml
mamba activate email-digest
pip install -e ".[dev]"
```

## Credentials

| What | Env var | Notes |
|---|---|---|
| Google OAuth token (Gmail API) | `GOOGLE_OAUTH_TOKEN` | Path to authorized-user JSON. Must grant **gmail.readonly** (unsubscribe + digest read) and **gmail.send** if you use topic `output.also_email_to` (digest emails yourself). Re-consent if you add `gmail.send` to an older token. |
| DeepSeek API key | `DEEPSEEK_API_KEY` | For digest LLM extraction/synthesis (`fast` / `smart`). If unset, the CLI also reads `deepseek.key` from `~/.local/share/opencode/auth.json`. Explicit env wins. |
| LM Studio base URL | `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` (optional local fallback) |
| LM Studio model id (fast local, default Qwen3.5 4B) | `LM_STUDIO_MODEL` | Must match LM Studio Local Server; on-disk preset `mlx-community/Qwen3.5-4B-MLX-4bit` (`local-chat` `src/llm.py`) |
| LM Studio model id (local synthesis, default Qwen3 4B Instruct) | `LM_STUDIO_MODEL_SMART` | Must match LM Studio; on-disk preset `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit` |
| Digest SQLite (optional override) | `DIGEST_CACHE_DB` | Defaults to `<repo>/cache/digest.sqlite` (gitignored) |

**Spark deep-links:** the digest uses `readdle-spark://openmessage?messageId=…` per the implementation plan. Readdle may change URL schemes; confirm on your device when convenient and update `src/email_digest/spark_link.py` if needed.

## CLI

```
# Unsubscribe
python -m email_digest unsubscribe              # same as `unsubscribe check`
python -m email_digest unsubscribe check [-d DAYS]

# Digest
python -m email_digest --version
python -m email_digest digest version
python -m email_digest digest topics
python -m email_digest digest topics --json
python -m email_digest digest topics --strict
python -m email_digest digest run ai --dry-run
python -m email_digest digest run ai --strict --dry-run
python -m email_digest digest run ai
python -m email_digest digest run --all [--dry-run]
python -m email_digest digest run --all --strict [--dry-run]
python -m email_digest digest run ai --cache-db /path/to/custom.sqlite
python -m email_digest digest cost
python -m email_digest digest cost --days 14 --cache-db /path/to/custom.sqlite
python -m email_digest digest cost --json
```

Cron / launchd: start from **`scripts/digest-cron.example.sh`** (set `GOOGLE_OAUTH_TOKEN`, optional `DIGEST_REPO` / `UNSUBSCRIBE_KEEP` / `DIGEST_CACHE_DB`).

`--dry-run`: JSON only (collect + extract + `trending`). **Without** `--dry-run`: adds LLM synthesis + self-contained HTML at `output/<topic>_<YYYY-MM-DD>.html` (and `synthesis` / `output_html` / optional `emailed_to` keys in the printed JSON). Per-message Gmail fetch or extraction errors are appended to **`output/_failures/<YYYY-MM-DD>.log`** (tab-separated lines); the run continues with the remaining messages. Use `--output-dir` / `--template-dir` to override defaults (failure logs live under the chosen output directory’s `_failures/`). Gmail OAuth is **not** loaded when the invocation is invalid (missing topic / `run` without `topic` or `--all`, or malformed `--since`). **`digest run --strict`** (single topic or **`--all`**) enforces the same YAML ``name`` == file stem rule as **`digest topics --strict`**; on mismatch, JSON `{ "topic", "file", "error" }` and exit **1**, and **single-topic** mismatches skip Gmail init. **`digest run <topic>`** on failure prints JSON `{ "topic", "file", "error" }` and exits **1** (missing/invalid YAML or pipeline exception). Bad **`--since`** shape exits **2** with a stderr message. **`digest run --all`**: prints a JSON array; if any topic fails (bad YAML, **`--strict`** stem mismatch, or pipeline error), that element is `{ "topic", "file", "error" }` and the process exits **1**; all success exits **0**.

## Docs

- `docs/PROJECT_BRIEF_EMAIL_SUMMARIES.md` — digest engine project brief
- `docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md` — implementation plan
- `docs/INVENTORY.md` — code inventory
- `docs/LESSONS_LEARNED.md` — Gmail API performance notes
