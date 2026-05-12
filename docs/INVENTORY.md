# Code Inventory — email-digest

This repo was created by merging the former `unsubscribe` project. All Gmail API, facade, SMTP, and utility code is already in `src/unsubscribe/`. The digest engine is being added as `src/email_digest/`.

---

## Already in repo (reusable as-is)

| File | Purpose | Used by |
|---|---|---|
| `src/unsubscribe/gmail_api_backend.py` | Gmail API read: `list_messages`, `get_message_html`, `get_message_body_text`, `strip_html_to_text`, `html_from_gmail_message_payload`, OAuth token refresh, threaded fetching | Both unsubscribe + digest |
| `src/unsubscribe/gmail_facade.py` | `GmailBackend` Protocol, `GmailFacade` error-wrapping, `GmailHeaderSummary` (Message-ID, From, Subject, Date, List-Unsubscribe) | Both |
| `src/unsubscribe/timed_run.py` | `TimedRun` monotonic progress timer, `format_progress_line` | Both |
| `src/unsubscribe/keep_list.py` | JSON-based persistent set (`load`, `save`, `add`, `is_kept`) — used for sender selection in digest | Both |

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
