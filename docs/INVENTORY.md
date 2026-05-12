# Code Inventory — email-digest

This repo was created by merging the former `unsubscribe` project. Gmail API + façade live in `src/unsubscribe/`; digest email (when enabled) uses the same OAuth token and `users.messages.send`, not SMTP. The digest engine is `src/email_digest/`. Milestone plan: `docs/IMPLEMENTATION_PLAN_EMAIL_SUMMARIES.md`.

---

## Already in repo (reusable as-is)

| File | Purpose | Used by |
|---|---|---|
| `src/unsubscribe/gmail_api_backend.py` | Gmail API: `list_messages`, `get_message_html`, `get_message_body_text`, `get_profile_email`, `send_html_email`, helpers, OAuth (`gmail.readonly` + `gmail.send`), threaded fetch | Both |
| `src/unsubscribe/gmail_facade.py` | `GmailBackend` Protocol, `GmailFacade` error-wrapping, `GmailHeaderSummary` (Gmail id, RFC822 `Message-ID` when listed, From, Subject, Date, List-Unsubscribe, snippet). | Both |
| `src/unsubscribe/timed_run.py` | `TimedRun` monotonic progress timer, `format_progress_line` | Both |
| `src/unsubscribe/keep_list.py` | JSON-based persistent set (`load`, `save`, `add`, `is_kept`) — **same file as unsubscribe** (`~/.unsubscribe_keep.json` by default in `cli.py`); digest uses **inverse semantics** (kept senders = digest sources, not unsubscribe targets). No second persistence file. | Both |

## Already in repo (partially reusable — need minor adaptation)

| File | What to adapt |
|---|---|
| `src/unsubscribe/classifier.py` | `is_unsubscribable_newsletter` → invert logic for `is_digestible` (keep vs discard) |
| `src/unsubscribe/cli.py` | Add `digest` subcommand alongside existing `unsubscribe` commands |

## To be built (new code for digest engine)

| Module | Path | Dependencies |
|---|---|---|
| LLM provider | `src/email_digest/llm.py` | litellm |
| Digest pipeline | `src/email_digest/pipeline.py` | Gmail API, LLM |
| Embeddings | `src/email_digest/embed.py` | sentence-transformers |
| Clustering | `src/email_digest/cluster.py` | hdbscan |
| Spark deeplinks | `src/email_digest/spark_link.py` | stdlib only |
| HTML renderer | `src/email_digest/render.py` | jinja2 |
| Synthesis prompt | `src/email_digest/synthesis.py` | litellm |
| SQLite cache | `src/email_digest/cache.py` | sqlite3 (stdlib) |
| Config loader | `src/email_digest/config.py` | pyyaml |

## Patterns to borrow from sibling projects

| Pattern | Source project | File |
|---|---|---|
| `_load_yaml()` — YAML → dict | swim | `src/swim/config/paths.py:76-83` |
| `repo_root()` — pyproject.toml walk-up | swim | `src/swim/common.py:10-37` |
| `load_prompt()` — Markdown section extraction | local-chat | `src/prompts.py:14-42` |
| Protocol+Facade pattern | billing-glugglejug | `src/googleads_invoice/gmail_facade.py` |
| DI-based orchestrator | billing-glugglejug | `src/googleads_invoice/run_month.py` |
| Secret-from-file-or-env | billing-glugglejug | `src/googleads_invoice/cli.py:66-84` |
| Qwen / LM Studio on-disk model dirs (`~/.lmstudio/models/...`) | local-chat | `src/llm.py` (`MODEL_VARIANTS` — default locals: **`4b`** = Qwen3.5-4B MLX, **`qwen3`** = Qwen3-4B-Instruct) |

## Performance

After `users.messages.list`, avoid long sequential `users.messages.get` chains — see `docs/LESSONS_LEARNED.md` (thread pool, thread-local clients, `max_workers == 1` for tests).
