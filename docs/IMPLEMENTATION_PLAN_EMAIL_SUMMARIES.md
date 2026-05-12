# Implementation Plan — email-digest (merged repo)

**Agent / LLM implementers:** each slice in this document MUST use the section checklist and phrasing rules in **`docs/AGENT_PLAN_CONTRACT.md`** (invariants, permissions table, caveats four-liner, follow-up table, acceptance commands). Underspecified slices are invalid handoffs.

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

## Plan status (scope outside individual slices)

| Area | Status | Notes |
|------|--------|--------|
| M2–M4 (digest engine, cache, synthesis, HTML) | **Shipped** in repo | Older plan sections are narrative; no separate contract blocks retrofitted unless we reopen a milestone. |
| M5 (cron, CLI polish, cost dashboard) | **Shipped** — see **Slice: M5** below | Acceptance is the contract of record. |
| **STILL OPEN** (below) | Product / env verification | Not blocking M5 merge; tracked as follow-ups in M5 slice. |

---

## M5: Cron, polish, cost dashboard

### Slice: M5 — Cron, polish, cost dashboard

- **Goal:** Operators can run digests on a schedule with predictable exit codes, machine-readable cost usage, validated topic YAMLs, and resilient per-message error logging—without loading Gmail OAuth when no topic work will run.

- **Non-goals:** Changing LLM models, Spark URL scheme, unsubscribe behavior, default topic YAML content, or widening Gmail query semantics. No live Gmail or live LLM calls in the default CI test suite.

- **Invariants:**
  - `python -m email_digest --version` and `python -m email_digest digest version` print the installed **`unsubscribe`** distribution version from `pyproject.toml` (exit **0**).
  - `digest cost` and `digest cost --json` exit **0** even when the cache file is missing; JSON includes `cache_missing`, `days`, `cache_db`, aggregate `calls` / `input_tokens` / `output_tokens` / `cost_usd`, plus **`by_alias`** and **`by_model`** arrays (same shapes as `email_digest.cache.cost_report_payload`).
  - `digest topics` exits **0** on success, **1** on invalid YAML or `--strict` stem mismatch, **2** if `--topics-dir` is missing or not a directory. `--json` emits a JSON array of `{ name, file, display_name }`; text mode prints tab-separated `name` and `display_name` per line.
  - `digest run <topic>`: success prints one JSON object and exits **0**; missing/invalid YAML, `--strict` stem mismatch, or pipeline exception prints `{ "topic", "file", "error" }` and exits **1**; malformed `--since` exits **2** with stderr. **Single-topic** config/strict failures MUST NOT call `GmailApiBackend.from_env`.
  - `digest run --all`: prints a JSON array in **sorted `*.yaml` filename order**; elements are either normal pipeline dicts or `{ "topic", "file", "error" }`; exit **1** if any topic failed, **0** if none failed. **Gmail OAuth MUST NOT load** when there is no topic that reaches `run_digest` (empty topics dir, all config failures, or all `--strict` stem mismatches).
  - Per-message collect/extract failures append one line to `<output_dir>/_failures/<YYYY-MM-DD>.log` (fields tab-separated: UTC timestamp, topic, Gmail message id, exception type, message); the topic run continues.

- **Coupling:** `src/email_digest/cli.py`, `src/email_digest/cache.py`, `src/email_digest/pipeline.py`, `scripts/digest-cron.example.sh`, `README.md` (CLI / cron section), `tests/test_digest_cli.py`, `tests/test_digest_pipeline.py`, `tests/test_cache.py` (if cost payload shape changes).

- **Preconditions:** Branch with M4 pipeline merged; env **`email-digest`** (`mamba`); `pip install -e ".[dev]"` from repo root. Secrets: **`GOOGLE_OAUTH_TOKEN`** (path), optional **`DEEPSEEK_API_KEY`**, **`DIGEST_CACHE_DB`** — names only.

- **Permissions & environment:**

| Class | Rule |
|--------|------|
| **Network** | MUST NOT require live Gmail or LLM in CI; tests use mocks / tmp SQLite / tmp dirs. |
| **Filesystem** | MAY write under `tmp_path`, `tests/`, `cache/`, `output/` in tests; example cron script documents repo paths. |
| **Git** | No `Co-authored-by` or `--trailer`; if hooks inject trailers, commit with empty `core.hooksPath` for that invocation. |
| **Shell** | Acceptance uses `mamba run -n email-digest python -m pytest tests/ -q` from repo root. |
| **Credentials** | No token values in repo or plan. |

- **Caveats & footguns:**
  1. **Symptom:** Cron job touches OAuth even when every topic failed at YAML load. **Cause:** `digest run --all` called `from_env` before the per-file loop. **Wrong fix:** skip OAuth only in tests. **Right fix:** build an ordered action list (error vs run); call `from_env` only if at least one `run` action exists (see `cli._digest_run`).
  2. **Symptom:** `digest cost --json` consumers break. **Cause:** Renaming or dropping keys in `cost_report_payload`. **Wrong fix:** partial JSON tests. **Right fix:** extend `tests/test_digest_cli.py` (and `test_cache.py` if needed) whenever the payload contract changes.
  3. **Symptom:** Strict mismatch still hits Gmail. **Cause:** `from_env` ordered before strict check on single-topic path. **Wrong fix:** assert in docs only. **Right fix:** keep config + strict validation before `from_env` for single-topic; tests assert `from_env` not called.
  4. **Symptom:** Failure log not found. **Cause:** `_failures` uses `output_dir` default vs override. **Wrong fix:** hard-code `output/`. **Right fix:** pass `output_dir` through CLI to `run_digest` consistently; test uses `tmp_path`.

- **Procedure:**
  1. Ensure `digest version` / `--version`, `digest cost [--json]`, `digest topics [--json|--strict]`, `digest run` / `--all` / `--strict`, per-message `_failures` logging, and `scripts/digest-cron.example.sh` match **Invariants** above.
  2. For `digest run --all`, implement ordered two-phase handling so Gmail loads only when at least one `run_digest` is required; preserve JSON array order.
  3. Add or adjust tests for Gmail skip on `--all` with zero runnable topics and for empty topics dir (`from_env` not called).
  4. Align README CLI/cron copy with behavior.
  5. Run full fast test suite.

- **Acceptance:** From repo root, `mamba run -n email-digest python -m pytest tests/ -q` → exit **0**.

- **Follow-ups:**

| ID | Item | Type | Blocker for next slice? |
|----|------|------|-------------------------|
| F1 | LM Studio model id alignment (`LM_STUDIO_MODEL` / `LM_STUDIO_MODEL_SMART`) | env / docs | no |
| F2 | On-device verification of Spark `readdle-spark://` scheme | manual | no |
| F3 | Sender allowlist UX (`~/.unsubscribe_keep.json`) | product | no |

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
