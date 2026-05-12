# Implementation Plan — email-digest (merged repo)

**Agent / LLM implementers:** each slice in this document MUST use the section checklist and phrasing rules in **`docs/AGENT_PLAN_CONTRACT.md`** (invariants, permissions table, caveats four-liner, follow-up table, acceptance commands). Underspecified slices are invalid handoffs.

The `unsubscribe` project was renamed to `email-digest`. The existing Gmail API backend, façade, and utilities in `src/unsubscribe/` are **shared** by both the unsubscribe and digest features. This plan covers adding the digest engine.

## Implementation progress (canonical status — read this first)

**Last updated:** 2026-05-13 — bump this date whenever you change **Remaining scope** or ship a user-visible slice.

This section is the **continuity contract** for any implementer (human or LLM): status here overrides informal chat. Named slices below hold acceptance tests and invariants; this section holds **what is done vs what is still in scope**.

### Shipped (summary)

| Milestone / slice | Delivered (high level) |
|-------------------|-------------------------|
| M2–M4 (narrative in doc) | Digest engine: `src/email_digest/*`, topics YAML, templates, pipeline, cache, LLM, HTML, Spark links, optional Gmail send |
| **M5** | CLI: `version`, `cost`/`--json`, `topics`, `run`/`--all`/`--strict`, deferred Gmail for `--all` when nothing runs, failure logs, cron example |
| **C** | `docs/LM_STUDIO_DIGEST.md`, `resolve_model_alias()` in `llm.py`, tests |
| **D** | Extra Spark URL encoding regression tests (contract frozen in CI) |
| **B** | `is_digest_source_candidate()` → delegates to `is_unsubscribable_newsletter` |
| **A** | `digest candidates <topic>` — Gmail list + JSON, no LLM |
| **E** | `digest candidates` adds `sender_key`, `keep_list_kept`, `--keep-list` (parity with `digest run` gate) |

**Acceptance command for “repo still healthy”:** `mamba run -n email-digest python -m pytest tests/ -q` → exit **0**.

### Remaining scope (prioritized)

**Order for implementers:** rows are sorted by **approximate implementation effort** (smallest first) for **code/product** work (**Pick** 1–4), then **operator / manual / deferred** (**Pick** 5–7). **Pick 8 (R8)** is **always last**: formal docs must **follow** shipped behavior—skip under tight LLM budget.

| Pick | ID | Item | Type | Status | Next step when resuming |
|------|----|------|------|--------|---------------------------|
| 1 | R3 | **`run_digest` uses `digest_source_candidate`** (filter, warn-only log, or rank) | pipeline | **Not shipped** | New slice: explicit user-visible behavior + tests; today pipeline only uses keep-list + query |
| 2 | R2 | **`digest candidates --all`** (every topic, one OAuth, ordered output) | CLI | **Not shipped** | New slice: mirror `digest run --all` ordering + Gmail deferral rules |
| 3 | R1 | **Keep-list mutations from digest CLI** (`digest keep add|remove`, batch from JSON, or TUI) | product / CLI | **Not shipped** | New slice (§7): goal = persist to `~/.unsubscribe_keep.json` only; tests with `tmp_path`; no duplicate store |
| 4 | R4 | **Digest “walkthrough” UX** (M2 §4 style: step through rows like unsubscribe flow) | product | **Not shipped** | Large slice or app; `digest candidates` JSON is the current substitute |
| 5 | R6 | **Real sender addresses in `topics/*.yaml`** | content | **Open** | Replace TODO senders; optional CI: fail if `TODO-` in senders (often **human** edits, minimal LLM) |
| 6 | R5 | **Spark scheme on-device check** | manual | **Open (F2)** | User verifies `readdle-spark://…` on hardware; code change only if Readdle contract differs (**no LLM** unless bug found) |
| 7 | R7 | **Minimax / `cheap` alias** | LLM | **Deferred** | Plan RESOLVED: skipped until endpoint known |
| 8 | R8 | **Formal §7 slice blocks for legacy M2–M4 headings** | docs | **Optional** | **After** code is stable; retrofit only if reopening those milestones—**defer if budget is tight** |

### Out of scope (unless plan is amended)

- Parallel Gmail collector (IMAP, etc.) — brief forbids
- Second keep-list / digest-only persistence file — brief forbids

### How to update this document when you ship work

1. Move or shrink rows in **Remaining scope**; add a row to **Shipped** (or extend an existing shipped row).
2. Set **Last updated** to the merge/commit date.
3. Add or refresh the **named slice** block (§7 template) for the work you merged; link it from **Shipped** if not already listed.

---

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

Canonical rows for **done vs remaining** live in **Implementation progress** at the top of this file. The table below is a short index.

| Area | Status | Notes |
|------|--------|--------|
| M2–M4 (digest engine, cache, synthesis, HTML) | **Shipped** in repo | Narrative sections only; see **Implementation progress → Shipped**. |
| M5 | **Shipped** | See **Slice: M5** |
| Slices C, D, B, A, E | **Shipped** | See **Implementation progress** + Post-M5 slice headings |
| **Remaining** | See **Implementation progress → Remaining scope** | Do not duplicate long lists here—edit the R1–R8 table there. |

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

**Post-M5:** Any new behavior needs its **own** named slice using the §7 template in `docs/AGENT_PLAN_CONTRACT.md` before implementation; do not extend M5 retroactively.

Implementation order for digest follow-ups (**smallest scope first**): **Slice C → Slice D → Slice B → Slice A** (each closes or narrows plan follow-ups F1–F3 where noted).

### Slice: C — LM Studio operator runbook + alias resolution surface

- **Goal:** Operators can see exactly which litellm model string digest aliases `local` / `local_smart` resolve to from the environment, without reading `llm.py`; on-disk Qwen presets stay documented as **defaults to aim for**, not hard-coded ids in code.
- **Non-goals:** Changing default DeepSeek aliases, adding live LM Studio HTTP calls in CI, or auto-detecting LM Studio’s UI model list.
- **Invariants:** `MODEL_ALIASES` keys `fast`, `smart`, `local`, `local_smart` unchanged; `_resolve_model` / `complete` behavior unchanged; `LM_STUDIO_MODEL` overrides `local`; `LM_STUDIO_MODEL_SMART` overrides `local_smart` with fallback to `LM_STUDIO_MODEL` then default string.
- **Coupling:** `src/email_digest/llm.py`, `docs/LM_STUDIO_DIGEST.md` (new), `README.md` (one link under Credentials), `tests/test_llm_resolve_alias.py` (new).
- **Preconditions:** M5 merged; env `email-digest`; `pip install -e ".[dev]"`.
- **Permissions & environment:**

| Class | Rule |
|--------|------|
| **Network** | MUST NOT (no LM Studio in tests). |
| **Filesystem** | Doc + tests only under repo. |
| **Git** | No trailers; empty `core.hooksPath` on commit if hooks inject. |
| **Shell** | `mamba run -n email-digest python -m pytest tests/ -q` → **0**. |

- **Caveats & footguns:**
  1. **Symptom:** Docs list folder names but LM Studio shows different strings. **Cause:** UI vs on-disk path mismatch. **Wrong fix:** hard-code UI strings in Python. **Right fix:** runbook tells operator to copy the **Local Server** model id into env vars.
  2. **Symptom:** `resolve_model_alias` diverges from `complete`. **Cause:** duplicate resolution logic. **Wrong fix:** two code paths. **Right fix:** one public wrapper calling existing `_resolve_model`.

- **Procedure:** 1) Add `resolve_model_alias` in `llm.py` delegating to `_resolve_model`. 2) Add `docs/LM_STUDIO_DIGEST.md` (env vars, id copy steps, Qwen preset targets, `digest cost` pointer). 3) Link from README. 4) Tests for env override + `local_smart` fallback chain.
- **Acceptance:** `mamba run -n email-digest python -m pytest tests/ -q` → exit **0**.
- **Follow-ups:** none (F1 narrowed to “operator follows runbook”; no code blocker).

### Slice: D — Spark deeplink contract (tests + frozen URL shape)

- **Goal:** The `readdle-spark://openmessage?messageId=<url-encoded RFC822>` contract is encoded in tests so accidental regressions fail CI; documentation states encoding rules.
- **Non-goals:** Changing the URL scheme or query key without on-device verification (F2); adding Spark app automation.
- **Invariants:** `spark_deeplink` return shape unchanged for existing callers; empty/whitespace input → `""`; non-empty uses `quote(..., safe='')` on the full RFC822 string (angle brackets included).
- **Coupling:** `tests/test_spark_link.py`, `docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md` (this slice), `README.md` only if the slice adds a one-line pointer to tests as contract.
- **Preconditions:** Slice C optional merge order independent.
- **Permissions & environment:** Same as C (pytest only).

- **Caveats & footguns:**
  1. **Symptom:** Links open wrong thread. **Cause:** double-encoding or stripping angle brackets. **Wrong fix:** guess encoding. **Right fix:** tests assert decoded `messageId` equals raw input `mid` (existing); add reserved-character cases only if they round-trip.

- **Procedure:** 1) Add tests for characters that require percent-encoding beyond angle brackets (e.g. `&`, space). 2) No `spark_link.py` change unless a test proves a bug (none expected).
- **Acceptance:** `mamba run -n email-digest python -m pytest tests/ -q` → exit **0**.
- **Follow-ups:** F2 remains manual device check.

### Slice: B — Digest-source classification helper

- **Goal:** Digest code can ask “does this header row look like a list/newsletter source?” using the **same** heuristics as unsubscribe’s `is_unsubscribable_newsletter`, without duplicating logic (brief: digest needs the inverse at **keep-list** semantics; classification signal is the same bulk/list shape).
- **Non-goals:** Wiring classification into `run_digest` filtering (that belongs in slice A or a later pipeline slice); changing `is_unsubscribable_newsletter` behavior; body HTML prefetch in CI.
- **Invariants:** `is_unsubscribable_newsletter` unchanged; new public API is a thin wrapper with an explicit digest-oriented name; all existing `test_classifier.py` tests still pass.
- **Coupling:** `src/unsubscribe/classifier.py`, `tests/test_digest_classifier.py` (new), `docs/INVENTORY.md` (optional one-line update).
- **Preconditions:** Slice D merged or parallel (no code dependency).
- **Permissions & environment:** pytest only; no Gmail.

- **Caveats & footguns:**
  1. **Symptom:** Digest marks personal mail as candidate. **Cause:** copied heuristics diverged from unsubscribe. **Wrong fix:** fork logic. **Right fix:** delegate to `is_unsubscribable_newsletter` only.

- **Procedure:** 1) Add `is_digest_source_candidate(...) -> bool` delegating to `is_unsubscribable_newsletter`. 2) Tests: equality to newsletter helper on representative headers; body-link flag parity.
- **Acceptance:** `mamba run -n email-digest python -m pytest tests/ -q` → exit **0**.
- **Follow-ups:** Pipeline may later filter or rank by this flag (separate slice if behavior-visible).

### Slice: A — `digest candidates` CLI (topic-scoped list + classification JSON)

- **Goal:** For a topic YAML, list Gmail messages matching the digest query and emit **JSON** with per-row `digest_source_candidate` (from slice B) plus headers needed to decide keep-list updates, without running extraction/LLM.
- **Non-goals:** Interactive TUI; mutating keep list from this command; `--all` topics in one invocation (defer); synthesis/HTML.
- **Invariants:** Exit codes align with `digest run` where applicable: missing topic file / config error → **1** with stderr or JSON error shape per CLI style; invalid `--since` → **2**; success → **0** + stdout JSON array. Gmail loads only after config parse succeeds (same spirit as single-topic `run`). JSON keys stable: at least `id`, `from`, `subject`, `date`, `rfc_message_id`, `digest_source_candidate` (**slice E** adds `sender_key`, `keep_list_kept`, and **`--keep-list`**).
- **Coupling:** `src/email_digest/cli.py`, `tests/test_digest_cli.py`, `README.md` (CLI one-liner), `docs/INVENTORY.md` (CLI table row optional).
- **Preconditions:** Slice B merged (import `is_digest_source_candidate`); `headers_from_summary` from `gmail_facade`.
- **Permissions & environment:** Tests mock `GmailApiBackend.from_env` / `GmailFacade`; no live Gmail in CI.

- **Caveats & footguns:**
  1. **Symptom:** Classification always false. **Cause:** `headers_from_summary` omits fields classifier needs. **Wrong fix:** re-fetch full messages. **Right fix:** map `GmailHeaderSummary` fields into the same header dict shape as unsubscribe uses (`headers_from_summary` already includes List-Unsubscribe when present).
  2. **Symptom:** OAuth on typo topic name. **Cause:** `from_env` before config load. **Wrong fix:** swallow errors. **Right fix:** load YAML first, then `from_env` (mirror `digest run` single-topic ordering).

- **Procedure:** 1) Add `digest candidates <topic>` argparse + `_digest_candidates`. 2) build query via `build_digest_gmail_query`; `facade.list_messages`. 3) Emit JSON array. 4) Tests with mocks. 5) README example.
- **Acceptance:** `mamba run -n email-digest python -m pytest tests/ -q` → exit **0**.
- **Follow-ups:** Interactive keep-list merge (F3 remainder); `digest candidates --all` (optional).

### Slice: E — `digest candidates` keep-list preview fields

- **Goal:** Each `digest candidates` JSON row shows whether the message’s **From** address is already in the shared keep file (same semantics as `run_digest` ingestion) plus a normalized **`sender_key`** for scripting, without mutating the keep file from this command.
- **Non-goals:** CLI flags to add/remove keep entries; changing `run_digest` filtering; avoiding `load_keep_list`’s “create empty JSON if missing” behavior (must match pipeline).
- **Invariants:** Exit codes unchanged from slice A. Every successful candidates row includes **`sender_key`** (`string` or JSON **`null`** when `From` cannot be parsed) and **`keep_list_kept`** (`bool`, same as `is_kept(keep_list, from_)`). **`--keep-list`** defaults to the same path as **`digest run`** (`~/.unsubscribe_keep.json`).
- **Coupling:** `src/email_digest/cli.py`, `tests/test_digest_cli.py`, `README.md`, `docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md`.
- **Preconditions:** Slice A merged.
- **Permissions & environment:** Same as slice A (mocked Gmail in CI).

- **Caveats & footguns:**
  1. **Symptom:** `keep_list_kept` always false. **Cause:** wrong `--keep-list` path vs the file used for `digest run`. **Wrong fix:** guess home path. **Right fix:** pass explicit `--keep-list` or document default parity with `digest run`.
  2. **Symptom:** `sender_key` null for valid mail. **Cause:** malformed `From` not parseable by `parseaddr`. **Wrong fix:** substring hacks. **Right fix:** treat as null and false for keep (matches `sender_key` / `is_kept` contract).

- **Procedure:** 1) Add `--keep-list` to `digest candidates` (default = `DEFAULT_KEEP_LIST_PATH`). 2) After topic config + strict checks, `keep = load_keep_list(path)`; each row adds `sender_key` and `keep_list_kept`. 3) Tests with two mocked rows and a temp keep file. 4) README one-line note.
- **Acceptance:** `mamba run -n email-digest python -m pytest tests/ -q` → exit **0**.
- **Follow-ups:** Optional `digest keep add …` slice (mutating).

---

## RESOLVED QUESTIONS

1. ~~Minimax/cheap~~ → Skipped for now
2. ~~Gmail OAuth token~~ → Same as billing-glugglejug, `GOOGLE_OAUTH_TOKEN` env var
3. ~~Gmail API porting~~ → Already in this repo (src/unsubscribe/)
4. ~~Sender allowlists~~ → Use unsubscribe-style candidate selection workflow
5. ~~Repo name~~ → email-digest (unsubscribe renamed)

## STILL OPEN

Cross-check with **Implementation progress → Remaining scope** (canonical). Bullets here are non-normative reminders.

- **`LM_STUDIO_MODEL`** / **`LM_STUDIO_MODEL_SMART`** — operator must match LM Studio Local Server strings; see `docs/LM_STUDIO_DIGEST.md` (Slice C).
- **Spark URL scheme** — ship `readdle-spark://openmessage?messageId=<url-encoded RFC822 Message-ID>`; on-device verification (**F2 / R5**); adjust `spark_link.py` if Readdle changes.
- **Sender selection** — `digest candidates` + keep flags shipped (**A, E**); interactive keep / walkthrough = **R1, R4** in **Implementation progress**.
