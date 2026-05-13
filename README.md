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
| LM Studio operator runbook (alias → env → presets) | — | **`docs/LM_STUDIO_DIGEST.md`** |
| Cheap / MiniMax API key (for OpenCode Go) | `CHEAP_API_KEY` | Also auto-read from `~/.local/share/opencode/auth.json` (`opencode-go` block). Set up with `opencode /connect` for OpenCode Go, or export the key from [opencode.ai/auth](https://opencode.ai/auth). |
| Cheap model id override | `CHEAP_MODEL` | Default `openai/minimax-m2.5` (Go plan); set to `openai/minimax-m2.7` for improved quality. |
| Cheap API base URL | `CHEAP_API_BASE` | Default `https://opencode.ai/zen/go/v1` (Go plan). |
| Digest SQLite (optional override) | `DIGEST_CACHE_DB` | Defaults to `<repo>/cache/digest.sqlite` (gitignored) |

**Spark deep-links:** the digest uses `readdle-spark://openmessage?messageId=…` per **`src/email_digest/spark_link.py`**. Readdle may change URL schemes; use **`python -m email_digest digest spark-check`** and **`docs/SPARK_DEVICE_CHECK.md`** for a paste test on your device, then update **`spark_link.py`** if the contract differs.

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
python -m email_digest digest candidates <topic> [--keep-list PATH]
python -m email_digest digest candidates --all [--keep-list PATH]
python -m email_digest digest keep add --from 'News <news@example.com>' [--subject SUBJECT] [--keep-list PATH]
python -m email_digest digest keep remove --from 'news@example.com' [--keep-list PATH]
python -m email_digest digest keep merge --file batch.json [--keep-list PATH]
python -m email_digest digest walkthrough <topic> [--body] [--all] [--keep-list PATH] [--since YYYY-MM-DD]
python -m email_digest digest run ai --cache-db /path/to/custom.sqlite
python -m email_digest digest cost
python -m email_digest digest cost --days 14 --cache-db /path/to/custom.sqlite
python -m email_digest digest cost --json
python -m email_digest digest spark-check [--message-id '<id@host>']
```

Topic YAML under **`topics/`** ships multi-sender **`example.com`** patterns (RFC2606); replace each topic’s **`senders`** with **`From`** addresses you actually receive before expecting Gmail matches.

Cron / launchd: start from **`scripts/digest-cron.example.sh`** (set `GOOGLE_OAUTH_TOKEN`, optional `DIGEST_REPO` / `UNSUBSCRIBE_KEEP` / `DIGEST_CACHE_DB`).

`--dry-run`: JSON only (collect + extract + `trending`). In **`digest run`** JSON, each **`messages`** item includes **`digest_source_candidate`** (list/newsletter-style header heuristic; same as **`digest candidates`**), whether or not **`--dry-run`**. When that flag is **false** and there is **no** cached extraction, the pipeline **does not** fetch message HTML or call the extraction LLM—it uses empty `key_claims` / `entities` / `numbers` (see **Slice G** in the implementation plan). **Without** `--dry-run`: adds LLM synthesis + self-contained HTML at `output/<topic>_<YYYY-MM-DD>.html` (and `synthesis` / `output_html` / optional `emailed_to` keys in the printed JSON). **`digest candidates <topic>`** / **`digest candidates --all`** list Gmail headers and print JSON: each successful topic is **`{ "topic", "file", "query", "rows" }`** where **`rows`** holds **`digest_source_candidate`**, **`sender_key`**, and **`keep_list_kept`** (same keep semantics as **`digest run`**; **`--keep-list`** defaults the same); **`--all`** emits a sorted array like **`digest run --all`** (success objects or **`{ "topic", "file", "error" }`**, exit **1** if any failure). No LLM. **`digest keep add`**, **`remove`**, and **`merge`** update that same keep-list JSON (defaults match **`digest run`**). **`digest walkthrough <topic>`** interactively steps through **digest-source candidate** messages for the topic query (**[Enter]** add sender, **[s]** skip, **[q]** quit; same keep file). **`--body`** prefetches plain-text message bodies in parallel (extra Gmail API calls) and shows a preview per message; without it, no body fetch occurs. **`--all`** walks through every topic in sorted YAML filename order, reusing one Gmail façade; config/strict errors printed to stderr, walkthrough continues to next topic; exit **1** if any topic failed, **130** on interrupt. Per-message Gmail fetch or extraction errors append one line to **`output/_failures/<YYYY-MM-DD>.log`** (tab-separated fields: UTC ISO timestamp, topic, Gmail message id, exception type, message); the run continues with the remaining messages. Use `--output-dir` / `--template-dir` to override defaults (failure logs live under the chosen output directory’s `_failures/`). Gmail OAuth is **not** loaded when the invocation is invalid (missing topic / `run` without `topic` or `--all`, or malformed `--since`), when **single-topic** config or **`--strict`** fails before work starts, when **`digest candidates`** has neither a topic nor **`--all`**, or bad `--since` / config / strict before listing, or when **`digest run --all`** or **`digest candidates --all`** would load no Gmail-backed work (empty `*.yaml` set, or every file fails YAML load or **`--strict`** before any run / list). **`digest run --strict`** (single topic or **`--all`**) enforces the same YAML ``name`` == file stem rule as **`digest topics --strict`**; on mismatch, JSON `{ "topic", "file", "error" }` and exit **1**. **`digest run <topic>`** on failure prints JSON `{ "topic", "file", "error" }` and exits **1** (missing/invalid YAML or pipeline exception). Bad **`--since`** shape exits **2** with a stderr message. **`digest run --all`**: prints a JSON array in sorted filename order; if any topic fails (bad YAML, **`--strict`** stem mismatch, or pipeline error), that element is `{ "topic", "file", "error" }` and the process exits **1**; all success exits **0**.

## Docs

- `docs/AGENT_PLAN_CONTRACT.md` — **how to write plan slices** (permissions, caveats, follow-ups, acceptance) so implementers do not guess
- `docs/PROJECT_BRIEF_EMAIL_SUMMARIES.md` — digest engine project brief
- `docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md` — implementation plan
- `docs/LM_STUDIO_DIGEST.md` — LM Studio env vars and model id alignment for digest aliases
- `docs/INVENTORY.md` — code inventory
- `docs/SPARK_DEVICE_CHECK.md` — paste **`digest spark-check`** URL into Spark (manual R5 / F2)
