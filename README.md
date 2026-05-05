# unsubscribe

Automating unsubscribe from unsolicited newsletters: Gmail shortlist → interactive review → optional one-click / body link / Brave batch.

## Setup

```bash
mamba env create -f environment.yml
mamba activate unsubscribe
pip install -e ".[dev]"
```

The dev extra includes `pytest` and `selenium` (for imports and local automation; CI runs the fast suite only).

### Browser batch (Selenium + Brave) — any machine

This is **optional**: one-click / header-only paths work without a browser. For the **Brave batch** (and page capture under `.unsubscribe_page_capture/`), another developer should:

1. Use the same `**pip install -e ".[dev]"`** (or `**[browser]`** from `pyproject.toml`) so **Selenium** is installed.
2. Set `**GOOGLEADS_BROWSER_DEBUGGER_ADDRESS`** (e.g. `127.0.0.1:9222`) — **same variable name as sibling project googleads-invoice-glugglejug** — and start Brave with that debug port (see **Quick start** / `**brave-gig`** below, or that repo’s `README` / `docs/REAL_WORKFLOW_AND_PREFLIGHT.md`).
3. `**browser_helpers.py`** only sets `**debuggerAddress`** and calls `**webdriver.Chrome(options=opts)**`, matching the neighbor’s attach helpers — no `ChromeService`, no `binary_location`, **no changing `PATH`**.

**Chromedriver stderr “147 vs 148” warning:** Selenium often prints that **Homebrew’s `chromedriver`** and the **version string it attributes to “Chrome”** disagree. If the run **continues** and you see steps like *Opening unsubscribe URL … in browser*, attach worked — treat the message like noise, same as the sibling project. **Brave’s Chromium can trail** the newest ChromeDriver line Google publishes.

**Real failure:** `**SessionNotCreatedException`** with “only supports Chrome *N*” vs “Current browser *M*” means **driver major and running Brave major** must be aligned (e.g. `brew upgrade chromedriver` **and/or** Brave until they match **your** live browser).

**About `PATH`:** Nothing in this repo edits your shell profile. A **short-lived mistake** in development **temporarily removed `/opt/homebrew/bin` from `PATH` only inside Python** during `WebDriver` startup; that confused Selenium’s driver choice and **is reverted**. **Do not** strip brew from `PATH` in forks — it is not part of the install story.

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


| Item   | Value                                                                                                                                                                                                                                             |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Path   | `~/.unsubscribe_keep.json` (hardcoded in this version)                                                                                                                                                                                            |
| Format | JSON object: sender key → `{ "subject", "date_kept" }` — **no email body or web page content** (Brave-batch page snapshots live under `**.unsubscribe_page_capture/`**; see README / `page_capture_base_dir()` in `unsubscribe_page_capture.py`). |


### Exit codes


| Code  | Meaning                                                                             |
| ----- | ----------------------------------------------------------------------------------- |
| `0`   | Normal completion (including **q** on automation prompt).                           |
| `1`   | Error (e.g. could not list Gmail messages).                                         |
| `130` | `KeyboardInterrupt` during the walkthrough / re-check (partial selections printed). |


### Quick start

Use the `**unsub`** shell alias from `~/.bash_aliases`: same shape as `**send-gig`** — `**brave-gig`**, `**sleep 3**`, `**mamba activate**` …, then the real entrypoint (`**&& googleads-invoice run-month**` vs `**&& cd "$unsub" && unsubscribe**`). The tool reads `**GOOGLEADS_BROWSER_DEBUGGER_ADDRESS**` (shared with **googleads-invoice-glugglejug**).

```bash
export GOOGLE_OAUTH_TOKEN="$HOME/.google/oauth_token.json"
# GOOGLEADS_BROWSER_DEBUGGER_ADDRESS often already in ~/.bash_aliases

unsub    # brave-gig → sleep 3 → env → cd clone → unsubscribe (default check flow)

# Or without the alias:
mamba activate unsubscribe && cd /path/to/unsubscribe && unsubscribe
unsubscribe check --days 7
unsubscribe --help
```

### Brave + Selenium (workflow)

Installer / chromedriver notes: see **Setup** → *Browser batch (Selenium + Brave) — any machine*.

Selenium **attaches** via `debuggerAddress`; it does not start the browser. `**brave-gig`** is only:

`open -a "Brave Browser" --args --remote-debugging-port=9222`

So `**unsub`** runs `**unsubscribe`** after the same Brave+wait+activate prelude as `**send-gig**`. For browser automation you still need `**GOOGLEADS_BROWSER_DEBUGGER_ADDRESS**` set to the same `host:port` (your aliases typically export it next to `**brave-gig**`).

Direct launch without the alias:

```bash
"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  --remote-debugging-port=9222
```

### Automation env (after the single confirmation prompt)


| Variable                             | When needed                                                                                                                                                                              |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GOOGLEADS_BROWSER_DEBUGGER_ADDRESS` | Same as neighbor repo: required for the **browser** batch here (e.g. `127.0.0.1:9222`). Often already in your shell profile next to `**brave-gig`**. If unset, browser URLs are skipped. |
| `UNSUBSCRIBE_SUBSCRIBER_EMAIL`       | Optional; visible empty `type=email` fields on preference-center pages are filled with this address before the main Unsubscribe click.                                                   |
| `UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR`   | Optional; directory for HTML+PNG failure traces (default: `~/Downloads`).                                                                                                                |
| `RUN_LIVE_BRAVE_TRACE`               | Optional; set to `1` to enable optional trace dumps in trace helpers.                                                                                                                    |


**Page capture:** When the Brave batch runs, artifacts go under `**.unsubscribe_page_capture/session_`***. From a source checkout, that base folder is the repo root (next to `src/`). From a wheel install, it is `**.unsubscribe_page_capture` in the directory you ran `unsubscribe` from** — `cd` to your clone first if you want captures beside the project. The console log line *Recording pages…* shows the full session path. **There is no capture when every message is handled by one-click POST alone, or when no message ends up with a browser URL** (no allowlisted body link **and** no `http`/`https` target in `List-Unsubscribe`). Otherwise you need the debugger address set, at least one queued browser URL, and automation confirmed.

### Maintainer tests (markers)

Same gate style as the neighbor repo:


| Variable                                                     | Purpose                                                   |
| ------------------------------------------------------------ | --------------------------------------------------------- |
| `RUN_E2E=1`                                                  | Enable `@pytest.mark.e2e` locally (skipped in CI).        |
| `RUN_LIVE_BRAVE=1` plus `GOOGLEADS_BROWSER_DEBUGGER_ADDRESS` | Enable `@pytest.mark.live_brave` locally (skipped in CI). |


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


