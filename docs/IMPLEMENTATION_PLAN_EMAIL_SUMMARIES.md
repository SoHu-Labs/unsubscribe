# Implementation Plan — email-digest (merged repo)

The `unsubscribe` project was renamed to `email-digest`. The existing Gmail API backend, façade, and utilities in `src/unsubscribe/` are **shared** by both the unsubscribe and digest features. This plan covers adding the digest engine.

## Repo structure (target)

```
src/
  email_digest/              # NEW — digest engine
    __init__.py
    llm.py                   # litellm provider (DeepSeek + Claude + LM Studio)
    pipeline.py               # orchestrator
    embed.py                  # sentence-transformers
    cluster.py                # HDBSCAN
    spark_link.py             # readdle-spark:// deeplinks
    render.py                 # Jinja2 → HTML
    cache.py                  # SQLite cache
    config.py                 # YAML topic config loader
  unsubscribe/               # existing (shared Gmail API, facade, utils)
    gmail_api_backend.py      # SHARED: Gmail API read
    gmail_facade.py           # SHARED: Protocol + Facade
    timed_run.py              # SHARED: progress timer
    keep_list.py              # SHARED: JSON persistence
    classifier.py
    execution.py
    ... (existing files unchanged)
topics/                       # NEW
  ai.yaml
  health_psy.yaml
templates/                    # NEW
  digest.html.j2
tests/
  test_spark_link.py          # NEW
  test_cluster.py             # NEW
  ... (existing tests unchanged)
src/unsubscribe/cli.py        # MODIFIED: add 'digest' subcommand
```

---

## M2: LLM module + fetch email candidates

### Step 1: Install litellm

Add `litellm` to the existing mamba env and `requirements.txt`.

### Step 2: `src/email_digest/llm.py`

```python
import litellm
import os

MODEL_ALIASES = {
    "fast":  "deepseek/deepseek-v4-flash",
    "smart": "deepseek/deepseek-v4-pro",
    # LM Studio (OpenAI-compatible): default local presets — ids from LM Studio UI
    "local":       os.environ.get("LM_STUDIO_MODEL", "openai/local-model"),       # Qwen3.5 4B MLX on disk
    "local_smart": os.environ.get("LM_STUDIO_MODEL_SMART", "openai/local-model"),  # Qwen3-4B-Instruct on disk
    # "cheap" skipped — minimax via opencode endpoint TBD
    # Anthropic Claude available via auth.json OAuth key
}
# On-disk reference (local-chat src/llm.py): ~/.lmstudio/models/mlx-community/Qwen3.5-4B-MLX-4bit
# and ~/.lmstudio/models/lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit

def complete(
    messages: list[dict],
    alias: str = "smart",
    *,
    max_tokens: int = 2000,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    ...
```

### Step 3: `src/email_digest/config.py`

Port `_load_yaml()` from swim. Load `TopicConfig` frozen dataclass from `topics/<name>.yaml`.

### Step 4: Fetch email candidates (like unsubscribe workflow)

Reuse `src/unsubscribe/gmail_api_backend.py::GmailApiBackend.list_messages` to fetch emails matching sender patterns. Show the user a list of candidates. User selects which to keep (inverse of unsubscribe: kept = digest sources). Persist selected senders in the **same keep file as unsubscribe** (default **`~/.unsubscribe_keep.json`**, `DEFAULT_KEEP_LIST_PATH` in `src/unsubscribe/cli.py`); **no** separate digest persistence path.

### Step 5: Unified CLI — `src/unsubscribe/cli.py`

Add `digest` subcommand to the existing unsubscribe CLI:

```bash
python -m email_digest digest run ai
python -m email_digest digest run --all
python -m email_digest digest run ai --dry-run
python -m email_digest digest run ai --since 2026-05-01
python -m email_digest digest cost        # LLM cost last 7 days
python -m email_digest digest topics       # list / validate topic YAMLs

# Existing unsubscribe commands remain:
python -m email_digest unsubscribe list
python -m email_digest unsubscribe dry-run
...
```

---

## M2 verification

```bash
python -m email_digest digest run ai --dry-run
# Should: fetch emails matching ai.yaml senders, dump JSON of extracted emails
```

---

## M3: Embedding cache + clustering

### `src/email_digest/cache.py` — SQLite

Tables: `extractions`, `embeddings`, `llm_calls`

### `src/email_digest/embed.py` — sentence-transformers

`all-MiniLM-L6-v2`, cache by claim hash.

### `src/email_digest/cluster.py` — HDBSCAN

Group claims by embedding similarity. Output trending themes.

---

## M4: Synthesis + HTML render

### Extraction prompt

```
Extract structured data from this email. Output JSON:
{
  "key_claims": [ ... ],   // 5-10 bullets
  "entities": [ ... ],
  "numbers": [ ... ]
}
```

### Synthesis prompt — use persona_prompt from topic YAML

### `src/email_digest/spark_link.py`

```python
from urllib.parse import quote

def spark_deeplink(message_id: str) -> str:
    return f"readdle-spark://openmessage?messageId={quote(message_id, safe='')}"
```

### `src/email_digest/render.py` + `templates/digest.html.j2`

Jinja2, single HTML file, inline CSS, dark mode default.

### Gmail API send for `also_email_to`

Send the rendered HTML with `users.messages.send` using the same OAuth token as read (`GOOGLE_OAUTH_TOKEN`); token must include **`gmail.send`** in addition to **`gmail.readonly`**. `"self"` resolves to `users.getProfile` → `emailAddress`.

---

## M5: Cron, polish, cost dashboard

- **`digest version`** / **`python -m email_digest --version`** — print installed wheel version (distribution name ``unsubscribe`` from ``pyproject.toml``).
- **`digest cost --json`** — machine-readable LLM usage summary (`cache_missing`, token totals, `cost_usd`, **`by_alias`** and **`by_model`** breakdowns) for scripts and cron.
- **`digest topics`** — list / validate `topics/*.yaml` (tab-separated or `--json`); **`--strict`** requires YAML ``name`` to match the file stem (CI), exit **1** on mismatch.
- **`digest run … --strict`** — same stem rule for **`digest run <topic>`** and **`digest run --all`**; JSON error + exit **1** on mismatch; single-topic mismatch does not initialize Gmail.
- **`digest run --all`** — runs every topic; JSON array mixes normal pipeline objects with `{ "topic", "file", "error" }` on failure; **exit 1** if any topic failed (cron-friendly).
- **Cron** — typical pattern: `cd <repo> && mamba run -n email-digest python -m email_digest digest run ai` on a schedule; ensure `GOOGLE_OAUTH_TOKEN` (and LLM keys) are available in that environment.

---

## RESOLVED QUESTIONS

1. ~~Minimax/cheap~~ → Skipped for now
2. ~~Gmail OAuth token~~ → Same as billing-glugglejug, `GOOGLE_OAUTH_TOKEN` env var
3. ~~Gmail API porting~~ → Already in this repo (src/unsubscribe/)
4. ~~Sender allowlists~~ → Use unsubscribe-style candidate selection workflow
5. ~~Repo name~~ → email-digest (unsubscribe renamed)

## STILL OPEN

- **`LM_STUDIO_MODEL`** / **`LM_STUDIO_MODEL_SMART`** — must match the model ids LM Studio’s Local Server exposes. **Defaults to standardize on:** (1) **Qwen3.5 4B MLX** → on-disk `mlx-community/Qwen3.5-4B-MLX-4bit` (`local` / extraction); (2) **Qwen3-4B-Instruct** → on-disk `lmstudio-community/Qwen3-4B-Instruct-2507-MLX-4bit` (`local_smart` / local synthesis). Paths from **`local-chat`** `src/llm.py` (`MODEL_VARIANTS`); UI strings may differ from folder names.
- **Spark URL scheme** — ship `readdle-spark://openmessage?messageId=<url-encoded RFC822 Message-ID>` as in this plan; **do not block** implementation on hardware. README notes on-device verification; adjust `spark_link.py` if Readdle’s scheme changes.
- **Sender selection** — user must review digest candidates; same **`~/.unsubscribe_keep.json`** workflow as unsubscribe with inverse semantics (see `docs/INVENTORY.md`).
