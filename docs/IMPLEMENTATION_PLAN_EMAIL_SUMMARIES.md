# Implementation Plan — email-digest (merged repo)

The `unsubscribe` project was renamed to `email-digest`. The existing Gmail API backend, facade, SMTP, and utilities in `src/unsubscribe/` are **shared** by both the unsubscribe and digest features. This plan covers adding the digest engine.

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
cli.py                        # MODIFIED: add 'digest' subcommand
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
    "local": "openai/local-model",
    # "cheap" skipped — minimax via opencode endpoint TBD
    # Anthropic Claude available via auth.json OAuth key
}

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

Reuse `src/unsubscribe/gmail_api_backend.py::GmailApiBackend.list_messages` to fetch emails matching sender patterns. Show the user a list of candidates. User selects which to keep (inverse of unsubscribe: kept = digest sources). Persist selected senders in `keep_list.json`.

### Step 5: Unified CLI — `cli.py`

Add `digest` subcommand to existing unsubscribe CLI:

```bash
python -m email_digest digest run ai
python -m email_digest digest run --all
python -m email_digest digest run ai --dry-run
python -m email_digest digest run ai --since 2026-05-01
python -m email_digest digest cost        # LLM cost last 7 days

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

### Gmail SMTP send for `also_email_to`

Reuse existing SMTP from `src/unsubscribe/` for emailing the HTML report.

---

## M5: Cron, polish, cost dashboard

---

## RESOLVED QUESTIONS

1. ~~Minimax/cheap~~ → Skipped for now
2. ~~Gmail OAuth token~~ → Same as billing-glugglejug, `GOOGLE_OAUTH_TOKEN` env var
3. ~~Gmail API porting~~ → Already in this repo (src/unsubscribe/)
4. ~~Sender allowlists~~ → Use unsubscribe-style candidate selection workflow
5. ~~Repo name~~ → email-digest (unsubscribe renamed)

## STILL OPEN

- LM Studio model name — user will specify
- Spark URL scheme verification — test on device
- Actual sender selection — user must review candidates
