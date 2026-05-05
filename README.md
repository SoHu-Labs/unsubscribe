# unsubscribe

Automating unsubscribe from unsolicited newsletters: Gmail shortlist → interactive review → optional one-click / body link / Brave batch.

## Setup

```bash
mamba env create -f environment.yml
mamba activate unsubscribe
pip install -e ".[dev]"
```

The dev extra includes `pytest` and `selenium` (for imports and local automation; CI runs the fast suite only).

## Credentials


| What                                                          | Env var              | Notes                                                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------------------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Google OAuth token (authorized user JSON, **Gmail readonly**) | `GOOGLE_OAUTH_TOKEN` | Path to the token file. Same variable as sibling project **googleads-invoice-glugglejug** — one token can serve both tools if scopes allow. Create/refresh with your existing OAuth flow (e.g. that repo’s `scripts/get_oauth_token.py` or any token that includes `https://www.googleapis.com/auth/gmail.readonly`). |


If `GOOGLE_OAUTH_TOKEN` is missing or empty, `unsubscribe check` fails when it tries to build the Gmail client.

## CLI

After install, the console script is `**unsubscribe`** (see `[project.scripts]` in `pyproject.toml`).

```
unsubscribe                  # same as `unsubscribe check`
unsubscribe -h, --help       # top-level help
unsubscribe check [--days N] # Gmail newer_than:Nd (default N=3)
unsubscribe check -h, --help
```

### Commands


| Command                          | Purpose                                                                                                                                                                                                                                                |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `unsubscribe`                    | Short for `**unsubscribe check**` (no subcommand required).                                                                                                                                                                                            |
| `unsubscribe check`              | List newsletters (last **N** days, default 3), walk through each new candidate, update `~/.unsubscribe_keep.json`, optionally reconsider previously kept senders, print selection summary, then **optionally** run automated unsubscribe (one prompt). |
| `unsubscribe check --days <int>` | Same as `check`, but sets **N** in `newer_than:Nd` (e.g. `--days 7`).                                                                                                                                                                                  |


### List line format

Each candidate row is printed as:

  `N. From : Subject :: short summary`

The summary is taken from the message body when possible, and skips common **preview boilerplate** (e.g. “view in browser”, signup lines) so the line shows the **article lede** rather than footer/unsubscribe copy.

### Interactive keys


| Phase                                           | Keys                                                                                                                                                                                               |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| New-candidate walkthrough                       | **k** — keep sender (saved to keep-list immediately); **Enter** — skip this message (no keep, no unsubscribe); **u** — mark for unsubscribe; **q** — quit walkthrough (**k**-keeps already saved). |
| Reconsider (overview)                           | After a **numbered list** of kept senders (same `Sender : Subject :: summary` style): **y** — walk through each row below; **Enter** or **k** — skip reconsider entirely (keep-list unchanged).    |
| Reconsider (per row)                            | **Enter** or **k** — keep (no change); **u** — mark for unsubscribe and remove from keep-list; **q** — skip remaining re-check rows.                                                               |
| After summary (if any selected for unsubscribe) | **Enter** — run automation (one-click → body link → Brave batch); **q** — skip automation.                                                                                                         |


### Keep-list file


| Item   | Value                                                  |
| ------ | ------------------------------------------------------ |
| Path   | `~/.unsubscribe_keep.json` (hardcoded in this version) |
| Format | JSON object: sender key → `{ "subject", "date_kept" }` |


### Exit codes


| Code  | Meaning                                                                             |
| ----- | ----------------------------------------------------------------------------------- |
| `0`   | Normal completion (including **q** on automation prompt).                           |
| `1`   | Error (e.g. could not list Gmail messages).                                         |
| `130` | `KeyboardInterrupt` during the walkthrough / re-check (partial selections printed). |


### Quick start

```bash
export GOOGLE_OAUTH_TOKEN="$HOME/.google/oauth_token.json"

# Optional: Brave remote debugging for the browser batch (only if you press Enter on the final automation prompt)
export UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS=127.0.0.1:9222

unsubscribe
unsubscribe check
unsubscribe check --days 7
unsubscribe --help
unsubscribe check --help
```

Start Brave with `--remote-debugging-port=9222` **before** accepting automation if you expect body/browser steps. Example (macOS):

```bash
"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  --remote-debugging-port=9222
```

### Automation env (after the single confirmation prompt)


| Variable                               | When needed                                                                                                                                                                               |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS` | Required for the **browser** batch (e.g. `127.0.0.1:9222`). If unset, one-click / mailto / body steps still run where possible; extracted browser URLs are skipped with a stderr message. |
| `UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR`     | Optional; directory for HTML+PNG failure traces (default: `~/Downloads`).                                                                                                                 |
| `RUN_LIVE_BRAVE_TRACE`                 | Optional; set to `1` to enable optional trace dumps in trace helpers.                                                                                                                     |


### Maintainer tests (markers)

Same gate style as the neighbor repo:


| Variable                                                       | Purpose                                                   |
| -------------------------------------------------------------- | --------------------------------------------------------- |
| `RUN_E2E=1`                                                    | Enable `@pytest.mark.e2e` locally (skipped in CI).        |
| `RUN_LIVE_BRAVE=1` plus `UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS` | Enable `@pytest.mark.live_brave` locally (skipped in CI). |


## Tests

```bash
pytest              # fast suite (no live browser)
pytest -q           # quiet
```

## Docs

- `[PLAN.md](PLAN.md)` — backlog, iteration status, env mapping vs googleads-invoice-glugglejug

## Contents


| Item               | Purpose                                                                                                                |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| `src/unsubscribe/` | Application package (`cli`, Gmail façade, classifier, keep-list, one-click, link extraction, browser batch, execution) |
| `tests/`           | Pytest suite and fixtures                                                                                              |
| `environment.yml`  | Mamba env (Python 3.12 + pip; then `pip install -e ".[dev]"`)                                                          |
| `PLAN.md`          | Detailed design and progress                                                                                           |


