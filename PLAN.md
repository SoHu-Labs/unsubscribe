# Newsletter unsubscribe assistant

Repo: [https://github.com/SoHu-Labs/unsubscribe](https://github.com/SoHu-Labs/unsubscribe)

## ⛔ READ THIS FIRST — IMPLEMENTATION INSTRUCTIONS

**Do not write any code until you have read this entire plan from top to bottom.**
Implement iterations **strictly in order** (1 → 2 → 3 → 4 → 5 → 6 → 7).
Each iteration depends on files created in earlier iterations. Do not skip ahead.

After each iteration, run `pytest -q`. All tests must pass before starting the
next iteration.

Before copying any file from the neighbor repo, **open and read the source file**
first. Do not implement from the plan's description — implement from the
actual source code in `../googleads-invoice-glugglejug/`.

**NEVER do these:**

- Never use `format="metadata"` expecting `snippet` — it's not there.
- Never copy a file without fixing `from googleads_invoice.` → `from unsubscribe.`.
- Never rename `GOOGLE_OAUTH_TOKEN` — both projects share one account, one token file.
- Never count a 200 POST response as "unsubscribed" — it only means "server accepted."
- Never create a file without verifying `__init__.py` exists in its package.
- Never skip creating test fixtures before writing production code.

## Goal

Automatically detect **new newsletter emails that have an unsubscribe link or
header** in Gmail from the **last 3 days**. Present them as a **numbered list**
showing **title, sender, and a short content summary** so the user can quickly
judge relevance. Then walk through **each email one at a time** with a slightly
**longer content summary** and a single-key decision: **Enter = keep** (skip),
**u or U = mark for unsubscribe**. After the walkthrough completes, **Brave
browser opens** and clicks each marked unsubscribe link **in sequence**
until all selected emails are unsubscribed.

**The tool remembers which newsletters you chose to keep**, so they won't appear
in future runs. During the walkthrough, previously-kept newsletters are shown
in a separate list. At the end, the tool also asks if you want to **reconsider
any previously-kept newsletters** for unsubscription (default: Enter = no change).

> **Summary:** one command → numbered list → interactive 1-by-1 review with
> content previews → persistent keep-list → end-of-run re-check of kept →
> brave opens and clicks all selected unsubscribe links.

**Discovery scope (Iterations 2–4):** The classifier accepts `has_body_unsubscribe_link` for forward compatibility, but the shortlist **never** sets it to `True` and **does not** fetch HTML bodies during discovery. Until a **post–Iteration-6 slice** adds a second pass (bulk-looking messages without `List-Unsubscribe` → fetch HTML → detect body link → re-run classifier), only **header-advertised** unsubscribe paths (`List-Unsubscribe` / `List-Unsubscribe-Post`) surface in the walkthrough. Body-only newsletters are **invisible** until that slice exists — deferred scope, not a bug.

**Execution prompt (Iterations 5–7):** After the walkthrough and re-check, the CLI prints the two-group selection summary, then **exactly one** prompt — `Press Enter to unsubscribe all N selected [q to quit]`. On Enter, run the **full** chain with **no further prompts**: RFC 8058 one-click POST → HTML link extraction for the remainder → Brave batch for what is still left. Iterations 5–6 ship **libraries + tests**; `**unsubscribe check` must not** gain a separate confirmation or partial execution path until Iteration 7 wires the unified flow.

## Flow

```
unsubscribe check  (one command)
  │
  ├─ 1. Gmail API: search last 3 days, fetch headers + short body snippet
  │
  ├─ 2. Classify: is this a newsletter AND does it have an unsubscribe path?
  │       (skip personal mail, transactional receipts, mail without unsubscribe)
  │
  ├─ 2b. Load keep-list: remove already-kept newsletters from candidates
  │       (stored in ~/.unsubscribe_keep.json)
  │
  ├─ 3. Display previously-kept list:
  │       Previously kept (will not be asked):
  │         · deals@shop.example — "Weekly Deals" (kept Apr 20)
  │         · news@daily.com — "Daily Brief" (kept Apr 22)
  │
  ├─ 4. Display numbered list of NEW candidates:
  │       1. [Subject] — [Sender] — [Short summary ~1 line]
  │       2. [Subject] — [Sender] — [Short summary ~1 line]
  │       ...
  │
  ├─ 5. Interactive walkthrough (one email at a time):
  │       ┌─────────────────────────────────┐
  │       │ #3  Subject: "Weekly Deals"     │
  │       │ From: deals@shop.example        │
  │       │ Date: Mon, 28 Apr 2026          │
  │       │                                 │
  │       │ This week: 40% off summer...    │
  │       │ plus free shipping on orders... │
  │       │                                 │
  │       │ [Enter] keep   [u] unsubscribe  │
  │       └─────────────────────────────────┘
  │       Enter → save sender to keep-list, move to next
  │       u/U   → mark for unsubscribe, move to next
  │
  ├─ 5b. Save keep-list: write newly-kept senders to ~/.unsubscribe_keep.json
  │
  ├─ 6. End-of-run re-check: ask about previously-kept newsletters
  │       "Reconsider any previously kept newsletters?"
  │       ┌─────────────────────────────────┐
  │       │ Previously kept: Weekly Deals   │
  │       │ From: deals@shop.example        │
  │       │ Kept on: 2026-04-20             │
  │       │                                 │
  │       │ [Enter] keep  [u] unsubscribe   │
  │       └─────────────────────────────────┘
  │       Default Enter = keep (no change to keep-list)
  │       u/U = mark for unsubscribe
  │
  ├─ 7. Collect selected: gather unsubscribe URLs/targets for all "u" picks
  │
  └─ 8. Execution + per-email report:
        For each selected email:
          try one-click POST first → if server responds 2xx:
            ⚠️  "server accepted (may need further steps)"
          ↗  if no one-click, extract body link → browser click →
            wait for confirmation text → ✓ "unsubscribed (page confirmed)"
          ✗  if browser finds no button / times out → ✗ "failed: (why)"
        Final summary: per-email status, not a misleading success count.
```

## Stack

Python 3.12+, **pytest**, **Gmail API**
(`google-api-python-client` + OAuth **authorized-user** token JSON), **HTTP
client** (stdlib `urllib` or `httpx` — pick one in the one-click slice),
optional **Selenium** for `@pytest.mark.e2e` paths (default skip in CI).
Package layout under `src/unsubscribe/`. **mamba:** root `environment.yml` (Python 3.12 + pytest) — after `mamba env create -f environment.yml` and `mamba activate unsubscribe`, run `pip install -e ".[dev]"` so the package is importable.

## Implementation progress (resume here)

Use this table to restart work without relying on chat history. **Status:** iterations **1–7** are implemented; extend via new slices / README if you add features.

**Columns:** **Goal** is the *user-facing “why this matters”* for each iteration (non-technical). The `**pytest`** column uses **✅** when the fast suite is green for that iteration. **Artifacts** lists what landed in the repo for engineers resuming cold.


| Iteration | Status   | `pytest` (local fast suite) | Goal (impact — why it matters)                                                                                                                                                                                                                                                                                                             | Artifacts / notes                                                                                                                                                                                                                                                                                          |
| --------- | -------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**     | **Done** | ✅                           | Establishes a trustworthy foundation: the project installs cleanly, tests run automatically on every change, and common credential files won’t get committed by mistake — so future work doesn’t erode quality or leak secrets silently.                                                                                                   | `pyproject.toml`, `src/unsubscribe/__init__.py` (`sanitize_filename`), `tests/test_smoke.py`, `tests/__init__.py`, `.gitignore` (incl. OAuth/token patterns), `.github/workflows/test.yml` (branch **main**), `environment.yml`                                                                            |
| **2**     | **Done** | ✅                           | Cuts inbox clutter *intelligently*: only messages that look like bulk mail **and** offer a real way to unsubscribe are candidates — personal mail, typical “transactional” alerts, and newsletters with no unsubscribe path stay out of your review queue.                                                                                 | `src/unsubscribe/classifier.py` (`is_unsubscribable_newsletter`), `tests/fixtures/headers/*.json` (5), `tests/test_classifier.py` (+ guard: body link without bulk signal → False)                                                                                                                         |
| **3**     | **Done** | ✅                           | Connects to **your** Gmail (read-only): the assistant can pull the subjects, snippets, and message content needed for previews—without you exporting mail or copy-pasting—while keeping the integration testable and safe in automation.                                                                                                   | `src/unsubscribe/gmail_facade.py`, `gmail_api_backend.py` (`GmailApiBackend`, readonly scope only), `tests/fixtures/gmail/metadata_message.json`, `minimal_message.json`, `tests/test_gmail_facade.py`, `tests/test_gmail_api_backend.py`; `pyproject.toml` deps `google-api-python-client`, `google-auth` |
| **4**     | **Done** | ✅                           | Delivers the core **interactive experience**: one command shows what’s new, walks you through each candidate with readable previews, remembers what you chose to keep, optionally revisits past “keeps,” and ends with an unambiguous summary of what you marked for unsubscribe—**before** any automated clicking or network unsubscribe. | `[project.scripts]` `unsubscribe`; `src/unsubscribe/keep_list.py`; `src/unsubscribe/cli.py` (`run_check`, `main`); `tests/test_keep_list.py`, `tests/test_cli_check.py`                                                                                                                                    |
| **5**     | **Done** | ✅                           | Honors senders who support **proper one-click unsubscribe** in the email headers: those can be completed quickly and predictably when you confirm—without opening a browser—while still failing loudly when the standard isn’t met.                                                                                                        | `src/unsubscribe/unsubscribe_oneclick.py` (`parse_list_unsubscribe`, `try_one_click_unsubscribe`, redirect rejection); `tests/fixtures/headers/oneclick_*.json` (4); `tests/test_unsubscribe_oneclick.py`                                                                                                  |
| **6**     | **Done** | ✅                           | Fills the gap when headers aren’t enough: finds a **reasonable unsubscribe link in the message body** with safety guardrails, so fewer newsletters stall as “can’t help” purely because the header was incomplete—still without blindly trusting arbitrary links.                                                                          | `src/unsubscribe/unsubscribe_link.py` (`extract_unsubscribe_link`, `HTMLParser` collector, ESP allowlist); `tests/fixtures/mail/*.html` (5); `tests/test_unsubscribe_link.py`                                                                                                                              |
| **7**     | **Done** | ✅                           | Closes the loop for the “messy” cases: **Brave** visits and clicks through the remaining unsubscribe flows in order, so you watch once instead of juggling tabs and confirmation pages—ending with a clear count of what succeeded vs failed.                                                                                              | `browser_helpers.py`, `live_brave_trace.py`, `browser_unsubscribe.py`, `execution.py`; `tests/conftest.py`, `tests/test_browser_unsubscribe.py`, `tests/test_execution.py`; CLI prompt + `skip_automation` for tests; `README.md` browser section; `pyproject.toml` dev + `selenium`                       |


**Resume commands (fresh shell):**

```bash
cd /path/to/unsubscribe
mamba env create -f environment.yml   # once; skip if env exists
mamba activate unsubscribe
pip install -e ".[dev]"
pytest
```

**Git / CI:** default branch is **main**; workflow `.github/workflows/test.yml` runs on `push` and `pull_request` to `main`. Verify GitHub Actions after pushing (manual).

## Delivery (agile, strict TDD)

- Thin **vertical slices** (~½–2 days), one logical **PR per slice**.
- **Strict TDD:** failing test → smallest implementation → green → refactor.
**No new production behavior** without a preceding red test (same bar as
[googleads-invoice-glugglejug PLAN.md](../googleads-invoice-glugglejug/PLAN.md)).
- **CI:** `pytest` on push/PR; fast suite green on default branch.

## Regression tests

- **Fast path (CI):** pure functions + adapters on **committed fixtures** under
`tests/fixtures/` (synthetic **Gmail API JSON** or **saved RFC 5322 /
parsed header** shapes — no live tokens in git).
- `**@pytest.mark.e2e`:** real browser / maintainer machine; **skip in CI**
unless you add a dedicated runner + secrets policy (mirror neighbor
`**RUN_E2E`** / `CI` gates).
- **Bugs:** add a failing fixture or unit test before fixing.

---

## ⚠️ CRITICAL: DO NOT REWRITE GMAIL — COPY FROM NEIGHBOR REPO

The project `**googleads-invoice-glugglejug`** (in the sibling directory
`../googleads-invoice-glugglejug`) already has working, tested Gmail OAuth
integration and Brave browser automation. **Do not write these from scratch.**
Copy the patterns directly and adapt only the differences listed below.

### ⛔ BEFORE YOU TOUCH ANY CODE — READ THESE FILES FIRST

Open and read these neighbor files **before** implementing anything.
Do not implement from memory or from this plan's descriptions.


| #   | Read this file                                                                 | You'll use it for                                                                 |
| --- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| 1   | `../googleads-invoice-glugglejug/src/googleads_invoice/gmail_facade.py`        | Protocol + Façade pattern (Iteration 3)                                           |
| 2   | `../googleads-invoice-glugglejug/src/googleads_invoice/gmail_api_backend.py`   | OAuth token, `build()`, `list_messages()`, `get_message_html()` (Iterations 3, 6) |
| 3   | `../googleads-invoice-glugglejug/src/googleads_invoice/billing_url.py`         | `HTMLParser` `<a href>` extraction (Iteration 6)                                  |
| 4   | `../googleads-invoice-glugglejug/src/googleads_invoice/browser_download.py`    | `chrome_driver_attach()`, options (Iteration 7)                                   |
| 5   | `../googleads-invoice-glugglejug/src/googleads_invoice/live_brave_download.py` | Full Brave flow, element-finding, click + wait (Iteration 7)                      |
| 6   | `../googleads-invoice-glugglejug/src/googleads_invoice/live_brave_trace.py`    | HTML+PNG trace on failure (Iteration 7)                                           |
| 7   | `../googleads-invoice-glugglejug/tests/conftest.py`                            | CI/env gating for e2e/live_brave markers (Iteration 7)                            |
| 8   | `../googleads-invoice-glugglejug/tests/test_gmail_facade.py`                   | Mocking pattern for GmailFacade tests (Iteration 3)                               |
| 9   | `../googleads-invoice-glugglejug/tests/test_live_brave_download.py`            | Mocking pattern for WebDriver tests (Iteration 7)                                 |


### ⛔ WHEN COPYING: fix these things every single time

Every time you copy a neighbor file, apply these 4 edits before testing:

1. **Change all import paths** — `from googleads_invoice.xxx` → `from unsubscribe.xxx`
2. **Change all env var names** — see [env var mapping table](#env-var-mapping) below. **Exception:** `GOOGLE_OAUTH_TOKEN` is shared — don't rename it.
3. **Change all `__init__.py` references** — add `src/unsubscribe/__init__.py` if missing
4. **Add dependencies to `pyproject.toml`** — see per-iteration dependency notes

### ⛔ ITERATIONS ARE STRICTLY SEQUENTIAL — DO NOT SKIP AHEAD

Each iteration **depends on files and classes created in previous iterations**.
You cannot implement Iteration 4 (`cli.py`) without the `GmailHeaderSummary`
dataclass from Iteration 3. You cannot implement Iteration 7 without the link
extraction from Iteration 6. **Always work from Iteration 1 → 7 in order.**

After completing each iteration, run `pytest -q` and confirm **all tests pass**
before starting the next iteration. Never begin Iteration N until Iteration N−1
has `pytest` green.

### ⛔ ALWAYS CREATE `__init__.py` FOR EVERY NEW PACKAGE

- `src/unsubscribe/__init__.py` — created in Iteration 1; must exist before any
other file under `src/unsubscribe/` can be imported.
- `tests/__init__.py` — create if missing; every new subdirectory under `tests/`
(e.g. `tests/fixtures/`) doesn't need its own `__init__.py`, but `tests/` does.

### What to copy (file-by-file)


| Neighbor file                                  | Role                                                                                                   | Our file name                            | What changes                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/googleads_invoice/gmail_facade.py`        | `GmailBackend` Protocol + `GmailFacade` error-wrapper                                                  | `src/unsubscribe/gmail_facade.py`        | **Fix imports** (`from googleads_invoice.` → `from unsubscribe.`), rename `GmailMessageSummary` → `GmailHeaderSummary`, add header+snippet fields.                                                                                                                                                                   |
| `src/googleads_invoice/gmail_api_backend.py`   | Real Gmail API backend: OAuth token → `build("gmail","v1")` → `list_messages()` + `get_message_html()` | `src/unsubscribe/gmail_api_backend.py`   | **3 changes:** (1) `list_messages()` makes **two** API calls: `format="metadata"`+`metadataHeaders` for headers AND `format="minimal"` for snippet, (2) add `get_message_body_text()` method, (3) drop send/smtp methods. Env var stays `GOOGLE_OAUTH_TOKEN` (**same as neighbor** — same account, same token file). |
| `src/googleads_invoice/billing_url.py`         | `HTMLParser`-based `<a href>` extraction from email HTML bodies                                        | `src/unsubscribe/unsubscribe_link.py`    | Replace `_BILLING_NETLOCS` Google-host allowlist with logic that finds links near "unsubscribe" / "opt-out" text.                                                                                                                                                                                                    |
| `src/googleads_invoice/browser_download.py`    | Reusable Selenium helpers: `build_chrome_options_for_remote_debugging()` + `chrome_driver_attach()`    | `src/unsubscribe/browser_helpers.py`     | Fix imports, keep `build_chrome_options_for_remote_debugging()` and `chrome_driver_attach()` only. Drop `build_chrome_options()`, `click_and_wait_for_pdf()`, download prefs.                                                                                                                                        |
| `src/googleads_invoice/live_brave_download.py` | Full flow: attach Brave → navigate → find element → click → wait-for-result                            | `src/unsubscribe/browser_unsubscribe.py` | Replace `_find_download_on_documents_page` with `_find_unsubscribe_element`, change `text()="Download"` → `text()="Unsubscribe"`, change `billing/documents` URL check → confirmation-page check.                                                                                                                    |
| `src/googleads_invoice/live_brave_trace.py`    | HTML+PNG dumps on failure                                                                              | `src/unsubscribe/live_brave_trace.py`    | Fix imports, change env var prefix (`GOOGLEADS_` → `UNSUBSCRIBE_`).                                                                                                                                                                                                                                                  |
| `tests/conftest.py`                            | CI/env gating for `e2e` / `live_brave` markers                                                         | `tests/conftest.py`                      | Copy structure, change marker names/env vars.                                                                                                                                                                                                                                                                        |


### ⛔ CRITICAL API GOTCHA: `snippet` is NOT in `format="metadata"`

The Gmail API returns different fields depending on `format=`:


| `format=` value | Returns `payload.headers`?       | Returns `snippet`? | Returns body?  |
| --------------- | -------------------------------- | ------------------ | -------------- |
| `"minimal"`     | ❌ No headers                     | ✅ Yes              | ❌ No           |
| `"metadata"`    | ✅ Yes (if `metadataHeaders` set) | ❌ **NO**           | ❌ No           |
| `"full"`        | ✅ Yes (all)                      | ✅ Yes              | ✅ Yes (base64) |


**This means you CANNOT use a single `format="metadata"` call and expect `snippet` to be present.** The solution:

```python
# ── In list_messages(): TWO calls per message ──

def list_messages(self, query: str, *, max_results: int = 50) -> list[GmailHeaderSummary]:
    list_resp = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    out: list[GmailHeaderSummary] = []
    for m in (list_resp.get("messages") or []):
        mid = m["id"]

        # Call 1: get headers (List-Unsubscribe etc.)
        meta = service.users().messages().get(
            userId="me", id=mid, format="metadata",
            metadataHeaders=[
                "List-Unsubscribe", "List-Unsubscribe-Post",
                "Subject", "From", "Date",
            ],
        ).execute()
        headers = {
            h["name"]: h["value"]
            for h in (meta.get("payload", {}).get("headers") or [])
        }

        # Call 2: get snippet (NOT available in metadata!)
        minimal = service.users().messages().get(
            userId="me", id=mid, format="minimal"
        ).execute()
        snippet = minimal.get("snippet", "")

        out.append(GmailHeaderSummary(
            id=mid,
            thread_id=meta.get("threadId", ""),
            from_=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            date=headers.get("Date", ""),
            snippet=snippet,
            list_unsubscribe=headers.get("List-Unsubscribe"),
            list_unsubscribe_post=headers.get("List-Unsubscribe-Post"),
        ))
    return out
```

**If you use a single `format="metadata"` call without also fetching `format="minimal"`, `snippet` will be empty and the walkthrough will show blank summaries.**

The rest of the token loading, refresh, error handling, and `build("gmail", "v1")`
flow is **identical** to the neighbor and should be copied as-is.

---

## Story map (summary)

**Epics (1:n):** each row is one **epic** named for **delivery order and scope**.
Several **user-valued outcomes** for that epic live in the **same cell** — read
top to bottom as **implementation sequence**.


| Epic                           | User outcomes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **E1 — Foundation & CI**       | Packaging, install path, and `**pytest` + CI** so later work ships with the same checks every merge — catch breakage before it lands.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **E2 — Discover & shortlist**  | **One command** (`unsubscribe check`) that searches Gmail for the **last 3 days**, finds newsletters **that have an unsubscribe link or header**, **removes previously-kept senders** from the local keep-list, and displays a **numbered list** with **title, sender, and short content summary** (~~1 line). **Previously-kept newsletters are shown in a separate list** so you know what won't be asked about.~~ ~~Then an **interactive walkthrough** — each email shown one at a time with a **slightly longer content summary** (~~5 lines) and a single-key prompt: **Enter = keep (saves to keep-list), u/U = mark for unsubscribe**. After the walkthrough, an **end-of-run re-check** asks about each **previously-kept** newsletter — **Enter = keep (default, no change), u/U = unsubscribe now**. The selected subset (from new walkthrough + re-check) is handed to the execution phase. |
| **E3 — Unsubscribe execution** | After the walkthrough + re-check, a **single confirmation prompt** shows the combined selections and asks: "Press Enter to unsubscribe all N selected [q to quit]". **No per-stage prompts** — one Enter triggers the full chain: one-click POST → body-link extraction → Brave batch-click. Brave opens once and clicks remaining links in sequence.<br>**Report per email, not a single number.** Each row shows which email, which method was tried, and the **exact outcome**. A 200 from a one-click POST does not mean "unsubscribed" — it means "server accepted the request, may require further steps." Only report unsubscription as confirmed when the browser flow detects confirmation text on the page. **Plain, actionable errors** — no silent failure, no misleading counts. |


### Traceability (epics → iterations)


| Epic                           | Iterations (delivery order)                                                             |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| **E1 — Foundation & CI**       | [Iteration 1](#iteration-1)                                                             |
| **E2 — Discover & shortlist**  | [Iteration 2](#iteration-2) · [Iteration 3](#iteration-3) · [Iteration 4](#iteration-4) |
| **E3 — Unsubscribe execution** | [Iteration 5](#iteration-5) · [Iteration 6](#iteration-6) · [Iteration 7](#iteration-7) |


---

## How to read each iteration

Every iteration has:


| Section                    | Meaning                                             |
| -------------------------- | --------------------------------------------------- |
| **Step-by-step checklist** | Exact things to do, in order. Check each off.       |
| **Epic**                   | Which epic this iteration belongs to.               |
| **Story**                  | What the user can do after this iteration ships.    |
| **In scope**               | What this iteration produces.                       |
| **Out of scope**           | What you must **not** build yet.                    |
| **Acceptance criteria**    | How to prove the iteration is done.                 |
| **Common mistakes**        | Pitfalls that have burned previous implementations. |


Implementation status: mark iterations **✅** when done, and keep the **[Implementation progress](#implementation-progress-resume-here)** table updated so anyone can resume from the repo alone.

Each iteration closes with **merged code**, `**pytest` green**, and **no live
Gmail / no real unsubscribe HTTP** unless the iteration explicitly says
"maintainer-only manual check."

---

### Iteration 1 — "Green pipeline" ✅


| Field                   | Detail                                                                                                                                                                                                                                                                |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Epic**                | **E1 — Foundation & CI**                                                                                                                                                                                                                                              |
| **Story**               | Reproducible install and **automated tests on PRs** so the codebase stays merge-safe before Gmail or unsubscribe logic lands.                                                                                                                                         |
| **In scope**            | `pyproject.toml` (package + dev deps), `src/unsubscribe/` package layout, one non-trivial smoke test (a pure function, not just `import`), `.gitignore`, GitHub Action running **pytest** on `**main`**, minimal `**environment.yml`** (mamba: Python 3.12 + pytest). |
| **Out of scope**        | Gmail, HTTP unsubscribe, browsers, real credentials, any code that talks to the network.                                                                                                                                                                              |
| **Acceptance criteria** | Fresh checkout → install editable + dev extras → `**pytest`** passes; CI workflow passes on `push`/`pull_request` to default branch.                                                                                                                                  |
| **Common mistakes**     | Forgetting `packages` in `[tool.setuptools.packages.find]` so `src/unsubscribe` isn't importable. Adding secrets/env files to git — check `.gitignore` before the first push.                                                                                         |


#### Step-by-step checklist

- 1. Create `pyproject.toml` with `[build-system]`, `[project]` (name=`unsubscribe`, requires-python>=3.12), `[project.optional-dependencies]` for dev (pytest), and `[tool.setuptools.packages.find]` pointing at `src/`.
- 1. Create `src/unsubscribe/__init__.py` with `sanitize_filename` and a test in `tests/test_smoke.py` that calls it (strict TDD).
- 1. Extend `.gitignore` for `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `dist/`, `*.pyc`, `.env`, token / OAuth JSON patterns.
- 1. Create `.github/workflows/test.yml` that runs `pip install -e ".[dev]" && pytest` on push/PR to `**main`**.
- 1. Add minimal `**environment.yml`** (mamba: Python 3.12 + pytest); post-create: `pip install -e ".[dev]"`.
- 1. Run `pip install -e ".[dev]" && pytest` locally — green.
- 1. Push to `**main**` (or open PR) and confirm GitHub Actions passes — **manual before merge**.

**Done when:** CI workflow exists for `**main`**, `pytest` runs locally in one command, no network calls in the test suite, `environment.yml` documents the dev env.

---

### Iteration 2 — "Newsletter classification (fixtures)" ✅


| Field                   | Detail                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Epic**                | **E2 — Discover & shortlist**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Story**               | The eventual list is **scoped to newsletters that have an unsubscribe capability** — i.e. both (a) looks like bulk/marketing mail and (b) has a `List-Unsubscribe` header OR a detectable unsubscribe link in the body. Non-newsletter mail and newsletters without any unsubscribe path are silently skipped.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **In scope**            | Pure function `is_unsubscribable_newsletter(headers: dict, has_body_unsubscribe_link: bool = False) -> bool`. Takes email headers (`From`, `Subject`, `Date`, `List-Unsubscribe`, `List-Unsubscribe-Post`, optional `Precedence: bulk`) plus a boolean flag for body-link detection. Returns `True` only if **both**: (a) looks like bulk/marketing (has `List-Unsubscribe` or `Precedence: bulk` or known bulk-sender patterns) AND (b) has an unsubscribe path (either `List-Unsubscribe` header present, or `has_body_unsubscribe_link=True`). **≥5 committed fixtures** under `tests/fixtures/headers/`: strong yes (newsletter with `List-Unsubscribe`), strong yes (newsletter, no header but body has link — `has_body_unsubscribe_link=True`), strong no (personal email, no headers), edge no (transactional receipt with `List-Unsubscribe` — GitHub/bank/etc.), edge no (newsletter with no unsubscribe path at all — `List-Unsubscribe` missing AND no body link). |
| **Out of scope**        | Gmail API, HTML body parsing for link detection (Iteration 6 and the deferred post–Iteration-6 discovery pass — for Iterations 2–4 the caller **never** sets `has_body_unsubscribe_link=True` during shortlist), network.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **Acceptance criteria** | `pytest -q` passes; all 5 fixtures locked; removing a fixture's expected result requires a deliberate code change; a newsletter without any unsubscribe path returns `False` (won't show in the list).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **Common mistakes**     | (1) Classifying everything with a `List-Unsubscribe` header as a newsletter — many transactional services (GitHub, bank, airline) include unsubscribe headers. Start with **restrictive** rules. (2) Forgetting the "has unsubscribe capability" check — if an email is clearly a newsletter but has NO unsubscribe header or link, we **cannot** help the user unsubscribe, so skip it. (3) Not reading the HTML body yet — that's Iteration 6, but the classifier must accept a flag from the caller indicating body-link detection result.                                                                                                                                                                                                                                                                                                                                                                                                                                  |


#### Step-by-step checklist

- 1. Create `src/unsubscribe/classifier.py` with function `is_unsubscribable_newsletter(headers: dict[str, str], *, has_body_unsubscribe_link: bool = False) -> bool`.
- 1. Create `tests/fixtures/headers/` directory.
- 1. Write fixture 1 — `newsletter_with_header.json`: newsletter headers with `List-Unsubscribe` (ESP marker). Expected: `True`.
- 1. Write fixture 2 — `newsletter_body_link_only.json`: no `List-Unsubscribe`, `Precedence: bulk`; caller passes `has_body_unsubscribe_link=True`. Expected: `True`.
- 1. Write fixture 3 — `personal_no.json`: person-to-person. Expected: `False`.
- 1. Write fixture 4 — `transactional_with_header.json`: GitHub-style with `List-Unsubscribe`. Expected: `False`.
- 1. Write fixture 5 — `newsletter_no_unsub_path.json`: `Precedence: bulk` but no unsubscribe path and `has_body_unsubscribe_link=False`. Expected: `False`.
- 1. Write `tests/test_classifier.py` with one test per fixture (plus extra guard: `has_body_unsubscribe_link=True` on personal mail stays `False`).
- 1. Run `pytest -q tests/test_classifier.py` — all green.
- 1. **Manual:** flip a classification rule locally and confirm a test fails (locks behavior).

**Done when:** Classification rules are tested. No Gmail API calls. No HTML parsing.

---

### Iteration 3 — "Gmail read adapter (protocol + façade)" ✅

**⚠️ COPY FROM NEIGHBOR — DO NOT WRITE FROM SCRATCH.**


| Field                   | Detail                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Epic**                | **E2 — Discover & shortlist**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Story**               | List data comes from **live Gmail** after normal OAuth — not manual exports.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **In scope**            | (1) `GmailBackend` Protocol + `GmailFacade` error-wrapper → **copy** neighbor's `gmail_facade.py`, then: (a) replace all `from googleads_invoice.` imports with `from unsubscribe.`, (b) rename `GmailMessageSummary` → `GmailHeaderSummary` with fields: `id`, `thread_id`, `from_`, `subject`, `date`, `snippet`, `list_unsubscribe`, `list_unsubscribe_post` (use `str                                                                                                                                                                                                                                                                                                                                       |
| **Out of scope**        | Sending mail, modifying labels, OAuth consent UI, browser. (`get_message_body_text()` uses the same full-message + payload helpers as HTML extraction; separate `format=full` fetch, not a call to `get_message_html()`.)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **Acceptance criteria** | Unit tests never touch network; facade wraps arbitrary exceptions into `GmailTransportError`; token file missing → clear `ValueError` mentioning the env var by name; test with committed fixture JSON simulating a `format="metadata"` Gmail API response verifies headers AND snippet are extracted; `get_message_body_text()` test verifies HTML stripping + truncation to ~500 chars.                                                                                                                                                                                                                                                                                                                       |
| **Common mistakes**     | (1) Using `format="minimal"` — you'll get snippets but no headers. (2) Using `format="metadata"` and expecting `snippet` — it's not there. You MUST make **two** API calls: `format="metadata"` for headers + `format="minimal"` for snippet. (3) Forgetting to fix import paths when copying — neighbor files say `from googleads_invoice.xxx`, you must change to `from unsubscribe.xxx`. (4) Changing the env var name — **don't**. Reuse `GOOGLE_OAUTH_TOKEN` (same var as neighbor). Both projects access the same Gmail account, same token file. (5) Including `gmail.modify` scope — stick to `gmail.readonly`. (6) Forgetting to add `google-api-python-client` and `google-auth` to `pyproject.toml`. |


#### Step-by-step checklist

- 1. **READ** neighbor `gmail_facade.py` / `gmail_api_backend.py` (source: `../googleads-invoice-glugglejug`).
- 1. `**src/unsubscribe/gmail_facade.py`:** `GmailHeaderSummary`, `GmailBackend` Protocol (`list_messages`, `get_message_html`, `get_message_body_text` only), `GmailFacade` error wrapping.
- 1. `**src/unsubscribe/gmail_api_backend.py`:** `GmailApiBackend`, `list_messages()` = **two** `get()` calls per id (`metadata` + `metadataHeaders` / `minimal` for snippet). `get_message_html()`, `get_message_body_text()` (strip HTML, ≤500 chars; `plaintext_from_gmail_message_payload` fallback).
- 1. Env `GOOGLE_OAUTH_TOKEN`; scopes **only** `gmail.readonly` (no `adwords`).
- 1. `pyproject.toml` dependencies: `google-api-python-client`, `google-auth`.
- 1. `tests/fixtures/gmail/metadata_message.json`, `minimal_message.json` — committed shapes for `messages().get()`.
- 1. `tests/test_gmail_facade.py`, `tests/test_gmail_api_backend.py` — mocks, no network.

**Done when:** `pytest` green; no live Gmail / tokens in repo.

---

#### Reference (historical checklist — superseded by boxes above)

- Neighbor copies **adapted** (not verbatim): dropped SMTP/send paths; renamed summary type; dual-fetch `list_messages`.

---

### Iteration 4 — "CLI: interactive review walkthrough" ✅


| Field                   | Detail                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Epic**                | **E2 — Discover & shortlist**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **Story**               | One command `unsubscribe check` searches Gmail last 3 days, filters to **header-advertised** unsubscribable newsletters, **removes previously-kept senders** (loaded from `~/.unsubscribe_keep.json`), displays **previously-kept newsletters in a separate list**, then shows a **numbered list of new candidates** with title, sender, short summary (~~1 line each). Walks through **each new email one at a time** with a **longer content summary** (~~5 lines); **Enter = keep** (persist keep-list **immediately**), **u = mark for unsubscribe**, **q = quit** (prior keeps already saved). After that loop, **end-of-run re-check** for each **previously-kept** sender; Enter = keep (no change), u/U = unsubscribe. Prints the **two labeled groups** + `**N total`**.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **In scope**            | CLI entrypoint (`[project.scripts]` → `unsubscribe check`). Wires: Gmail search (`newer_than:3d`) → `facade.list_messages()` → `is_unsubscribable_newsletter(headers_from(m))` **with `has_body_unsubscribe_link=False` always** (no body fetch for discovery) → **load keep-list** from `~/.unsubscribe_keep.json` → filter out kept senders using `sender_key(from_header)` (`None` → skip keep matching for that row) → display kept list separately → for each new candidate, call `facade.get_message_body_text(id)` (walkthrough preview only) → numbered list display (index, subject, sender, 1-line snippet) → `input()` loop: Enter → **incremental** keep-list write; u/U; q → **end-of-run re-check** → print **two labeled groups** + `N total` (see checklist). No actual unsubscription yet. `pytest` with fake backend + mocked `input()` + `tmp_path`. If zero new candidates, print the "No new newsletters…" line and still run re-check.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **Out of scope**        | Performing unsubscribe actions (that's E3). Opening Brave. Sending HTTP.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **Acceptance criteria** | `pytest` asserts: stable numbered list format including content summary; keep-list read/write + **incremental** persist on each Enter; `sender_key()` / malformed `From` behavior; kept-sender filtering; walkthrough: `u`/`U`, invalid keys re-prompt, `**q` preserves prior Enter-saves**; re-check: Enter = no-change; **final summary**: `Selected for unsubscribe:` / `New: #…` / `Kept (reconsidered): sender (Subject)` / `N total`; `--help`; exit code 0.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **Common mistakes**     | (1) Not fetching body text for the walkthrough — the initial list uses `snippet` from `GmailHeaderSummary`, but the walkthrough needs ~5 lines. Call `facade.get_message_body_text(id)` for each candidate before starting the walkthrough. (2) Using `is_newsletter_candidate()` instead of `is_unsubscribable_newsletter()` — the function was renamed in Iteration 2, imports must match. (3) Instability in numbering — sort once at the start by date descending, assign numbers, never reorder. (4) Printing raw HTML — `get_message_body_text()` already strips tags; if modifying, don't undo that. (5) Not handling Ctrl+C — wrap walkthrough in `try: ... except KeyboardInterrupt:` and print partial selections (Enter-saves already on disk if using incremental persist). (6) Forgetting to handle `snippet` being empty — Gmail `snippet` can be `""` for short emails; fall back to first 80 chars of body text. (7) **Keep-list key**: `email.utils.parseaddr(from_header)` → addr part, strip, lower — not subject or message ID. If parseaddr returns `('', '')`, `sender_key` is `None` — skip keep matching for that row (no crash). (8) **Keep-list file location**: use `Path.home() / ".unsubscribe_keep.json"` — hardcode this, don't make it configurable yet. Create the file if it doesn't exist (empty JSON object `{}`). (9) **End-of-run re-check**: must default to Enter = keep (no change to keep-list). Only u/U removes from keep-list. (10) **Body-only discovery**: do not set `has_body_unsubscribe_link=True` during the Iteration 4 shortlist — that remains a deferred post–Iteration-6 slice. |


#### Step-by-step checklist (completed)

- `pyproject.toml` — `[project.scripts]` `unsubscribe = "unsubscribe.cli:main"`.
- `keep_list.py` — `sender_key`, `is_kept`, `load_keep_list` (create `{}` if missing), `save_keep_list`, `add_to_keep_list`, `remove_from_keep_list` (no-op when `sender_key` is `None`).
- `cli.py` — `main` / `run_check(days, facade=..., keep_list_path=..., input_fn=...)`; query `newer_than:{days}d -in:chats`; classify with `has_body_unsubscribe_link=False`; sort by `Date` desc; numbered list + walkthrough + incremental saves; `q` ends walkthrough early but continues to re-check; re-check with `q` skip remaining; two-group summary; `KeyboardInterrupt` → partial selections + exit 130.
- Tests: `tests/test_keep_list.py`, `tests/test_cli_check.py` (fake backend, scripted `input`).

---

#### Reference (original granular checklist)



Expand

- 1. Add `[project.scripts]` entry in `pyproject.toml`: `unsubscribe = "unsubscribe.cli:main"`.
- 1. Create `src/unsubscribe/keep_list.py` with functions:
  `sender_key(from_header: str) -> str | None` — calls `email.utils.parseaddr(from_header)`, returns `addr.strip().lower()`. Returns `None` if parseaddr yields `('', '')` (malformed From — skip keep-list matching, no error).
   `is_kept(keep_list: dict, from_header: str) -> bool` — `False` if `sender_key(from_header)` is `None`; else `True` if key is in `keep_list`.
   `load_keep_list(path: Path) -> dict[str, dict]` — returns `{sender_lower: {"subject", "date_kept"}, ...}`, creates empty `{}` file if missing.
   `save_keep_list(path: Path, data: dict) -> None`.
   `add_to_keep_list(path: Path, from_header: str, subject: str) -> None` — extracts sender key, adds entry, saves.
   `remove_from_keep_list(path: Path, from_header: str) -> None` — extracts sender key, removes entry, saves.
- 1. Create `src/unsubscribe/cli.py` with `main()` using `argparse`. Subcommand `check` with `--days` argument (default 3).
- 1. Build Gmail query: `"newer_than:{days}d"`. Add `-in:chats` to skip GChat. Call `facade.list_messages(query, max_results=50)`.
- 1. Filter candidates: `[m for m in messages if is_unsubscribable_newsletter(headers_from(m), has_body_unsubscribe_link=False)]` — **always** `False` here (no HTML body fetch in discovery until the deferred post–Iteration-6 pass).
- 1. Load keep-list from `~/.unsubscribe_keep.json`. Remove candidates whose `sender_key(m.from_)` is in the keep-list (if `sender_key` is `None`, do not treat as kept).
- 1. Display previously-kept list: `"Previously kept (will not be asked):"` + each entry with sender, subject, date-kept. If empty, skip this section.
- 1. If new candidates list is empty: `print("No new newsletters with unsubscribe links found in the last {days} days.")`. Do not exit yet — still run the end-of-run re-check.
- 1. For each new candidate, call `facade.get_message_body_text(m.id)` to get the ~500-char plain-text body. Store in dict.
- 1. Display numbered list of new candidates: each row shows index, subject, sender, 1-line snippet. If snippet empty, fall back to first 80 chars of body text.
- 1. Walkthrough loop for new candidates: for each email, print separator, show index, subject, from, date, ~5-line body preview, prompt `[Enter] keep  [u] unsubscribe  [q] quit`.
- 1. Use `input()`: Enter → add sender to keep-list AND **write keep-list file immediately** (incremental save), move to next. `u`/`U` → add to selected list, move to next. `q` → stop walkthrough (prior Enter-picks already saved). Anything else → re-prompt.
- 1. After new-candidate walkthrough, save keep-list to file (write `~/.unsubscribe_keep.json`).
- 1. End-of-run re-check: if keep-list has entries, print `"Reconsider any previously kept newsletters?"` then loop through each kept entry showing sender, subject, date-kept, prompt `[Enter] keep (no change)  [u] unsubscribe`.
- 1. Re-check input: Enter → skip (default, no change); `u`/`U` → add sender to selected list AND remove from keep-list; `q` → skip remaining re-check entries.
- 1. After re-check, save keep-list again (in case entries were removed).
- 1. Print exactly (adjust values):
  ```
  Selected for unsubscribe:
    New: #2, #5
    Kept (reconsidered): deals@shop.example (Weekly Deals)
  2 total
  ```
  Omit `New:` or `Kept (reconsidered):` lines when that group is empty. **`N total`** = combined count of both groups.
- 1. Wrap entire walkthrough + re-check in `try: ... except KeyboardInterrupt: print("\nInterrupted. Partial selections:", selected)`.
- 1. Write `tests/test_keep_list.py`: test load/save with `tmp_path`, verify dedup by sender, verify file-creation-if-missing.
- 1. Write `tests/test_cli_check.py`: use fake backend returning 5 test `GmailHeaderSummary` objects, pre-populated keep-list file, mock `input()` via `unittest.mock.patch`. Assert: kept-list filtering removes matching senders, kept list displayed, walkthrough order, Enter saves to keep-list, re-check shows kept entries, final output includes both walkthrough and re-check selections.
- 1. Test `--days 7` changes query to `newer_than:7d`.
- 1. Test zero-new-candidates: still runs re-check, doesn't crash.
- 1. Test `q` during walkthrough: verify incremental keep-list saves for prior Enter-picks are preserved in file, partial selections printed.
- 1. Test keep-list key parsing: verify `email.utils.parseaddr()` extracts `addr` from `"Display Name" <email@example.com>` and bare `email@example.com`. Verify `parseaddr` returning `('', '')` (malformed From) → entry skipped for keep-list matching (no error, no crash).

**Done when:** `unsubscribe check` prints kept list + numbered list of new candidates + walks through each new email + saves keeps incrementally to `~/.unsubscribe_keep.json` + runs end-of-run re-check + prints combined selections in two labeled groups (`"New: #2, #5"` / `"Kept (reconsidered): sender (Subject)"`). Enter saves to keep-list immediately, u/U marks, q quits preserving prior saves, Enter on re-check defaults to no-change. All verified in tests with fake backend and temp keep-list file.



---

### Iteration 5 — "RFC 8058 one-click + header parsing" ✅


| Field                   | Detail                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Epic**                | **E3 — Unsubscribe execution**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Story**               | Header-based **one-click** unsubscribe where the sender advertises it; **clear failure** when the message does not support that path.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **In scope**            | Parse `List-Unsubscribe` header (RFC 2369) — extract URL(s) and/or mailto:. Detect `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058). For one-click: send `POST` to the unsubscribe URL with body `List-Unsubscribe=One-Click`. Implement as a pure function or small class, fully mocked HTTP in CI (mock `urllib.request` or `httpx`). For `mailto:` arms: detect and print "manual action required: send email to X" — do not send mail in this iteration.                                                                                                                                                                                                                                               |
| **Out of scope**        | CAPTCHA flows, JavaScript-only preference centers, automated mailto sending, HTML body fallback (Iteration 6). `**unsubscribe check` confirmation or any unsubscribe execution** — Iteration 7 only.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **Acceptance criteria** | No network in CI; wrong/missing headers → typed, actionable errors (e.g. `NoUnsubscribeHeaderError`, `UnsubscribeNotOneClickError`); valid `List-Unsubscribe` + `List-Unsubscribe-Post` → mocked POST verified with correct URL and body; `mailto:` → clear stdout message with the address. **Reporting**: result for each attempted one-click must show the HTTP status and a truthful message — "server accepted (200) — may require further steps", not "unsubscribed". Never claim success from a POST response alone. |
| **Common mistakes**     | (1) Parsing `List-Unsubscribe` naively — the header value can be a **single** URL, a **comma-separated** list, or have angle brackets `<https://...>`. Strip angle brackets but don't assume they're always present. (2) Confusing RFC 2369 (the header itself) with RFC 8058 (the POST method) — `List-Unsubscribe` alone means the URL exists; `List-Unsubscribe-Post: List-Unsubscribe=One-Click` means you can POST to it. Without the Post header, the URL might require a browser. (3) Sending POST with wrong Content-Type — RFC 8058 specifies `application/x-www-form-urlencoded` or nothing. (4) Following redirects automatically on POST — don't. If the POST returns 3xx, report it, don't silently follow. |


#### Step-by-step checklist (completed)

- `unsubscribe_oneclick.py` — `parse_list_unsubscribe`, `try_one_click_unsubscribe`; case-insensitive header keys; HTTPS-only for POST; `Content-Type: application/x-www-form-urlencoded`; `_RejectRedirects` so 3xx raises `UnsubscribePostRedirectError`.
- Fixtures: `oneclick_yes.json`, `oneclick_no_post_header.json`, `oneclick_mailto_only.json`, `oneclick_malformed.json`.
- Tests: `tests/test_unsubscribe_oneclick.py` (mock `_urlopen_no_redirect`).
- No CLI / `unsubscribe check` wiring yet (Iteration 7).

---

#### Reference (original granular checklist)



Expand

- 1. Create `src/unsubscribe/unsubscribe_oneclick.py` with function `parse_list_unsubscribe(header_value: str) -> list[str]` that handles angle brackets, commas, whitespace, and returns a list of clean URLs/mailtos.
- 1. Add function `try_one_click_unsubscribe(headers: dict) -> str` that: checks `List-Unsubscribe-Post` for `List-Unsubscribe=One-Click`, finds the first HTTPS URL (not mailto) in `List-Unsubscribe`, sends POST, returns success message or raises typed error.
- 1. Write `tests/fixtures/headers/` JSON files: `oneclick_yes.json` (both headers present), `oneclick_no_post_header.json` (has `List-Unsubscribe` but no Post header), `oneclick_mailto_only.json` (only mailto, no HTTPS), `oneclick_malformed.json` (garbage header value).
- 1. Write `tests/test_unsubscribe_oneclick.py` mocking HTTP with `unittest.mock.patch` on whatever HTTP client you use. Verify: correct POST URL, correct body, typed error on missing headers, mailto detected and reported.
- 1. **Do not** add a confirmation prompt or execution branch to `unsubscribe check` in this iteration — that is **Iteration 7** (single prompt, full chain). This iteration **Done when** the module is complete and fully tested in isolation.

**Done when:** `parse_list_unsubscribe` + `try_one_click_unsubscribe` work in tests with mocked HTTP; clear typed errors; no real HTTP in CI. Iteration 7 will call `try_one_click_unsubscribe` from the unified execution path after the one confirmation.



---

### Iteration 6 — "HTML fallback: unsubscribe link extraction" ✅


| Field                   | Detail                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Epic**                | **E3 — Unsubscribe execution**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **Story**               | When headers are insufficient, derive a **usable HTTPS unsubscribe URL** from the **body** when trustworthy; **reject** unsafe or ambiguous cases with an explicit error.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **In scope**            | (1) `get_message_html()` / payload helpers already landed in **Iteration 3**; re-copy or reconcile here only if Iteration 3 left gaps. (2) Pure function `extract_unsubscribe_link(html: str) -> str` using stdlib `HTMLParser` — **copy pattern** from neighbor's `billing_url.py` but replace host filtering with link text/title/aria-label matching ("unsubscribe", "opt-out", "manage preferences", "email preferences", etc.). Safety: allowlist known ESP domains; reject `javascript:` / `data:` / IP / private ranges. (3) `tests/fixtures/mail/` with ≥3 HTML files (happy, ambiguous, malicious). (4) **Deferred (separate slice):** second discovery pass using body fetch for headerless bulk mail — **out of scope** for this iteration. |
| **Out of scope**        | Following the extracted link (that's the browser path in Iteration 7 or a future `GET` request iteration). OCR, JavaScript rendering.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Acceptance criteria** | `pytest -q` locks the link extraction per fixture; `javascript:` URIs raise `UnsafeLinkError`; IP-address URLs raise `UnsafeLinkError`; no link found raises `NoUnsubscribeLinkError` with a message suggesting the browser fallback.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Common mistakes**     | (1) Copying neighbor's `_BILLING_NETLOCS` host allowlist — that only matches Google domains. You need your own list of known email platform domains. (2) Assuming the unsubscribe link text always says "unsubscribe" — some senders use "manage preferences", "update your email", or just a bare URL. Start with text-matching and expand via the JS fallback pattern from the browser layer if needed. (3) Forgetting to decode base64 in the MIME payload — use `base64.urlsafe_b64decode` with padding fix (copy neighbor's `_urlsafe_b64decode` helper exactly). (4) Using `format="full"` when you don't need the body — only call `get_message_html()` for messages where one-click failed. Don't download every body upfront.                 |


#### Step-by-step checklist (completed)

- Read neighbor `billing_url.py`; implemented `_UnsubscribeAnchorCollector` (stacked `<a>` text + `title` / `aria-label`).
- `unsubscribe_link.py` — `extract_unsubscribe_link`, ESP allowlist (suffix match), `https` only, reject `javascript` / `data` / IP-literal hosts, wording gates per PLAN.
- `tests/fixtures/mail/` — five HTML fixtures + `tests/test_unsubscribe_link.py` (incl. `title=` signal, unknown host, `data:`).
- No CLI wiring (Iteration 7).

---

#### Reference (original granular checklist)



Expand

**⚠️ COPY HTML PARSING PATTERN FROM NEIGHBOR — ADAPT HOST FILTERING.**

- 1. **READ** neighbor's `billing_url.py` (`_AnchorHrefCollector`) before implementing. Confirm `gmail_api_backend.py` already has `get_message_html` / payload helpers from **Iteration 3**; only patch backend if something is missing.
- 1. Create `src/unsubscribe/unsubscribe_link.py` with `extract_unsubscribe_link(html: str) -> str`. **Copy** the `_AnchorHrefCollector(HTMLParser)` class from neighbor's `billing_url.py` (fix imports). Add safety filtering: reject `javascript:` URIs, `data:` URIs, IP-address hostnames, private IP ranges (10.x, 172.16-31.x, 192.168.x). Add an allowlist of known-safe marketing platform domains (mailchimp.com, substack.com, convertkit.com, etc. — start small, expand later). Only return a link if it passes safety checks AND its link text/aria-label/adjacent text matches "unsubscribe", "opt-out", "opt out", "manage preferences", "email preferences", "update subscription".
- 1. Create `tests/fixtures/mail/` with HTML files:
  - `newsletter_with_unsubscribe_link.html` — realistic newsletter HTML with a visible "Unsubscribe" link.
  - `newsletter_no_unsubscribe_link.html` — newsletter HTML with no unsubscribe link (only social media links).
  - `newsletter_ambiguous.html` — multiple links, none clearly unsubscribe.
  - `newsletter_javascript_link.html` — an `<a href="javascript:void(0)">` unsubscribe link.
  - `newsletter_ip_link.html` — link to `https://192.168.1.1/unsubscribe` (IP-literal host must raise `UnsafeLinkError`; **https** exercises the IP check, not the http scheme gate).
- 1. Write `tests/test_unsubscribe_link.py` with one test per fixture, asserting correct extraction or error type.
- 1. **Do not** wire execution into `unsubscribe check` here — **Iteration 7** runs `get_message_html` → `extract_unsubscribe_link` inside the unified post-confirmation chain. Optionally add a **private** helper used by Iteration 7 if that keeps `cli.py` thin.

**Done when:** `extract_unsubscribe_link` is tested with committed fixtures; unsafe links rejected; safe links returned. No browser automation; no extra CLI prompts.



---

### Iteration 7 — "Brave batch-unsubscribe (opens and clicks all selected links)" ✅


| Field                   | Detail                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Epic**                | **E3 — Unsubscribe execution**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **Story**               | After the walkthrough completes, **Brave opens** and **clicks each selected unsubscribe link in sequence** — the user watches as each link is visited and the unsubscribe button clicked. No manual copy-paste, no tab hunting. At the end: report "Unsubscribed from X of Y selected." If a link can be handled without the browser (RFC 8058 one-click POST from Iteration 5), do that first and only open Brave for the remaining links.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **In scope**            | (1) **Copy** `browser_download.py` → `src/unsubscribe/browser_helpers.py` — `build_chrome_options_for_remote_debugging()` + `chrome_driver_attach()` only. (2) **Copy structure** from `live_brave_download.py` into `src/unsubscribe/browser_unsubscribe.py` — attach Brave **once**, batch URLs, quit **once**. (3) **Copy** `live_brave_trace.py` → `src/unsubscribe/live_brave_trace.py` (env prefix `UNSUBSCRIBE_…`). (4) `tests/conftest.py` — gating for `@pytest.mark.e2e` / `@pytest.mark.live_brave`; use `**RUN_E2E`** and `**RUN_LIVE_BRAVE`** exactly as the neighbor repo (no rename). (5) README: Brave startup + env var table. (6) **Wire `unsubscribe check` execution:** after the two-group summary, **one** prompt (`Press Enter to unsubscribe all N selected [q to quit]`). On Enter → `try_one_click_unsubscribe` (Iteration 5) per applicable message → `get_message_html` + `extract_unsubscribe_link` (Iteration 6) for those still needing a URL → `batch_browser_unsubscribe` for the rest. **No per-stage prompts.**                                                   |
| **Out of scope**        | Automating every third-party marketing site reliably. Solving CAPTCHAs. Headless mode (preference centers often require visible browser).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **Acceptance criteria** | Default `pytest` fast (all browser tests skipped); `RUN_E2E=1` + `UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS=127.0.0.1:9222` enables browser tests on maintainer machine; unit tests mock `WebDriver` and verify: (a) Brave attaches **once** not per-URL, (b) `driver.get(url)` called for each link in order, (c) click called on each found element, (d) `driver.quit()` only after **all** URLs processed, (e) failure on one link continues to next (with error logged, not crash). **Reporting**: per-email status, not a single success count. For browser-confirmed unsubscription: "✓ unsubscribed (page showed 'you have been unsubscribed')". For browser attempt with no confirmation: "⚠ clicked button but no confirmation seen". For failure: "✗ failed: (specific reason)". README has exact Brave startup command. |
| **Common mistakes**     | (1) Quitting and re-attaching Brave between each link — attach once, batch-process all URLs, quit once. (2) Quitting Brave on a single link failure — log the error, continue to next link. Partial success is expected. (3) Copying selectors verbatim (`text()="Download"`) without changing to unsubscribe text. Change every occurrence to "Unsubscribe", "unsubscribe", "Opt out", "opt-out", "Manage preferences", "manage preferences". (4) Using the IDE's embedded browser instead of the user's Brave — only `debuggerAddress` attach to user's Brave is valid for logged-in sessions. (5) Not handling iframes — some preference centers load in an iframe. Copy neighbor's iframe-switching pattern (`driver.switch_to.frame(...)`) and after clicking, `driver.switch_to.default_content()`. (6) Not saving traces on failure — always save HTML+PNG before moving to next link. (7) Assuming all preference centers have the same confirmation signal — some show a green banner, some change the URL to `/unsubscribed`, some show a modal. Make confirmation detection configurable. |


#### Step-by-step checklist (completed)

- `browser_helpers.py` — remote-debug attach only (no download prefs).
- `live_brave_trace.py` — `UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR`; stem prefix `unsubscribe_`.
- `browser_unsubscribe.py` — `batch_browser_unsubscribe`, `print_unsubscribe_report`, iframe + unsubscribe selectors.
- `execution.py` — one-click → body link → browser batch; optional debugger for browser only.
- `tests/conftest.py` — `RUN_E2E` / `RUN_LIVE_BRAVE` + `UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS` (no deeplink gate).
- `tests/test_browser_unsubscribe.py`, `tests/test_execution.py`; CLI `skip_automation` + automation tests.
- `cli.py` — single post-summary prompt; resolve reconsidered rows from search window via sender+subject.
- `README.md` — Brave command + env table.
- `pyproject.toml` — `selenium` in `dev` + `browser` extra.
- `headers_from_summary` moved to `gmail_facade.py` for shared use.

---

#### Reference (original granular checklist)



Expand

**⚠️ COPY BROWSER PATTERNS FROM NEIGHBOR — ADAPT FOR UNSUBSCRIBE.**

- 1. **READ** neighbor's `browser_download.py`, `live_brave_download.py`, `live_brave_trace.py`, and `tests/conftest.py` before implementing.
- 1. **Copy** `browser_download.py` → `src/unsubscribe/browser_helpers.py`. Fix imports (`from googleads_invoice.` → `from unsubscribe.`). Keep `build_chrome_options_for_remote_debugging()` and `chrome_driver_attach()` as-is. Drop `build_chrome_options()` (fresh browser not needed) and `click_and_wait_for_pdf()` (PDF-specific). Drop `download_dir` prefs (not downloading files).
- 1. **Copy** `live_brave_trace.py` → `src/unsubscribe/live_brave_trace.py`. Fix imports. Change env var: `GOOGLEADS_LIVE_BRAVE_TRACE_DIR` → `UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR`.
- 1. Add to `pyproject.toml` optional dependencies: `selenium`.
- 1. Create `src/unsubscribe/browser_unsubscribe.py` with `batch_browser_unsubscribe(urls: list[dict], *, debugger_address: str, timeout_per_url_s: float = 30) -> list[dict]`. Each input dict has `{url, email_index, subject, sender}`. Follow neighbor's per-URL flow but **loop**:
  Attach **once**: `driver = chrome_driver_attach(debugger_address=debugger_address)`
   For each URL:
  - `driver.get(url)`
  - Handle tabs: `if len(driver.window_handles) > 1: driver.switch_to.window(driver.window_handles[-1])`
  - Wait for page ready
  - Handle iframes
  - Find element: **copy** neighbor's `_find_download_on_documents_page` as `_find_unsubscribe_element(driver)`. Change selectors: `"Download"` → `"Unsubscribe"`, `"unsubscribe"`, `"Opt out"`, `"Confirm unsubscribe"`, `"Yes, unsubscribe me"`.
  - Click: `element.click()`
  - Wait for confirmation (text check or URL change)
  - On failure: `save_live_brave_trace(driver, label=f"unsubscribe_{url_hash}")`, record failure, **continue** to next URL
   **Quit once** at end: `driver.quit()` in `finally`
   Return list of outcome dicts: `[{email_index, subject, sender, method: "browser", status: "confirmed"|"clicked-no-confirmation"|"failed", detail: str}, ...]`
- 1. In the same file, add `print_unsubscribe_report(results: list[dict])` that prints a per-email table. Each row: index, subject, sender, method tried (one-click / browser), and **exact outcome** — not "success" or "failed". Format:
     #2  "Weekly Deals" — deals@shop.example
         one-click POST → server accepted (200)
         ⚠ may require further steps (check your inbox)
     #5  "Daily Brief" — news@daily.com
         browser → button clicked → "unsubscribed" confirmation seen ✓
     #7  "Gadget Weekly" — noreply@gadgets.com
         browser → ✗ failed: no unsubscribe button found on page
   Then a summary line: "3 attempted: 1 confirmed, 1 server-acknowledged, 1 failed."
- 1. Write `tests/test_browser_unsubscribe.py` using mocked `WebDriver`. **READ** neighbor's `test_live_brave_download.py` for the mocking pattern, adapted for batch:
  Mock `chrome_driver_attach` returns a single `MagicMock` driver
   Verify `driver.get()` called N times (once per URL)
   Verify `.click()` called N times
   Verify `driver.quit()` called **exactly once**
   Test failure-continuation: one URL's element not found → error logged, remaining URLs still processed
- 1. **Copy** `conftest.py` → `tests/conftest.py` from neighbor. Fix imports. Change env var names (`GOOGLEADS_BROWSER_DEBUGGER_ADDRESS` → `UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS`, etc.). Keep CI gating logic identical.
- 1. Wire into CLI: after walkthrough + re-check, print combined selection summary (two labeled groups), then **one confirmation prompt**: `"Press Enter to unsubscribe all N selected [q to quit]"`. On Enter: for each selected email, try one-click first (if header-capable) → if one-click not available or returns non-2xx, try body-link extraction → if link found, browser click. Collect per-email outcome dicts: `{index, subject, sender, method, status, detail}`. After all emails processed, call `print_unsubscribe_report()`. **No per-stage prompts, no misleading success count.**
- 1. Write README section "Browser unsubscribe" with: Brave startup command, env var table, and the batch flow description.

**Done when:** `pytest` skips browser tests in CI; unit tests verify batch pattern (attach once, process all, quit once, failure continues); README documents workflow; maintainer can run real batch unsubscribe against their Brave with selected links from the walkthrough.



---

## Gmail integration — copy reference

### Files to copy vs. files to write


| File                                      | Action                                                   | Source                                                                         |
| ----------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `src/unsubscribe/gmail_facade.py`         | **COPY** then adapt dataclass fields                     | `../googleads-invoice-glugglejug/src/googleads_invoice/gmail_facade.py`        |
| `src/unsubscribe/gmail_api_backend.py`    | **COPY** structure, change `format=`                     | `../googleads-invoice-glugglejug/src/googleads_invoice/gmail_api_backend.py`   |
| `src/unsubscribe/unsubscribe_link.py`     | **PATTERN-COPY** from billing_url.py, change host filter | `../googleads-invoice-glugglejug/src/googleads_invoice/billing_url.py`         |
| `src/unsubscribe/browser_helpers.py`      | **COPY** attach/options functions                        | `../googleads-invoice-glugglejug/src/googleads_invoice/browser_download.py`    |
| `src/unsubscribe/browser_unsubscribe.py`  | **NEW** using neighbor's flow structure                  | `../googleads-invoice-glugglejug/src/googleads_invoice/live_brave_download.py` |
| `src/unsubscribe/live_brave_trace.py`     | **COPY** verbatim, change env prefix                     | `../googleads-invoice-glugglejug/src/googleads_invoice/live_brave_trace.py`    |
| `tests/conftest.py`                       | **COPY** structure, change env var names                 | `../googleads-invoice-glugglejug/tests/conftest.py`                            |
| `src/unsubscribe/classifier.py`           | **WRITE** from scratch (no neighbor equivalent)          | —                                                                              |
| `src/unsubscribe/keep_list.py`            | **WRITE** from scratch (no neighbor equivalent)          | —                                                                              |
| `src/unsubscribe/cli.py`                  | **WRITE** from scratch (no neighbor equivalent)          | —                                                                              |
| `src/unsubscribe/unsubscribe_oneclick.py` | **WRITE** from scratch (no neighbor equivalent)          | —                                                                              |


### Env var mapping


| Neighbor env var                     | Our env var                                                               | Purpose                                                    |
| ------------------------------------ | ------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `GOOGLE_OAUTH_TOKEN`                 | `GOOGLE_OAUTH_TOKEN` (**same as neighbor** — one token file, one account) | Path to OAuth authorized-user token JSON                   |
| `GOOGLEADS_BROWSER_DEBUGGER_ADDRESS` | `UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS`                                    | Brave remote debugging address (e.g. `127.0.0.1:9222`)     |
| `GOOGLEADS_LIVE_BRAVE_TRACE_DIR`     | `UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR`                                        | Directory for HTML+PNG failure traces                      |
| `RUN_LIVE_BRAVE`                     | `RUN_LIVE_BRAVE` (**same as neighbor**)                                   | Enable live Brave tests (muscle memory; no prefix)         |
| `RUN_E2E`                            | `RUN_E2E` (**same as neighbor**)                                          | Enable end-to-end browser tests (muscle memory; no prefix) |


### The one call you must change

Neighbor's `list_messages()` uses a single `format="minimal"` call:

```python
# NEIGHBOR (one call, snippet only — DON'T COPY DIRECTLY):
detail = service.users().messages().get(
    userId="me", id=m["id"], format="minimal"
).execute()
# → detail["id"], detail["threadId"], detail["snippet"]
```

You must replace it with **two calls** — one for headers, one for snippet:

```python
# OUR CODE (two calls — headers + snippet):

# Call 1: get headers
meta = service.users().messages().get(
    userId="me", id=mid,
    format="metadata",
    metadataHeaders=[
        "List-Unsubscribe", "List-Unsubscribe-Post",
        "Subject", "From", "Date",
    ],
).execute()
headers = {
    h["name"]: h["value"]
    for h in (meta.get("payload", {}).get("headers") or [])
}

# Call 2: get snippet (NOT available in format="metadata"!)
minimal = service.users().messages().get(
    userId="me", id=mid, format="minimal"
).execute()
snippet = minimal.get("snippet", "")

# Combine into your dataclass:
GmailHeaderSummary(
    id=mid,
    thread_id=meta.get("threadId", ""),
    from_=headers.get("From", ""),
    subject=headers.get("Subject", ""),
    date=headers.get("Date", ""),
    snippet=snippet,
    list_unsubscribe=headers.get("List-Unsubscribe"),
    list_unsubscribe_post=headers.get("List-Unsubscribe-Post"),
)
```

Everything else (token loading, refresh, error wrapping, `build()`) stays
**exactly the same** as the neighbor.

---

## Unsubscribe page capture — case catalog & handler methods

**Purpose:** Field runs that execute the **Brave browser batch** produce `session_*` directories under **`.unsubscribe_page_capture/`** (see README and `unsubscribe_page_capture.py`) containing `manifest.json` (per-step **primary_category**, **evidence_tags**, **page_url**, **step**, HTML). This section is the **canonical backlog** for turning those observations into automation: each **case** has a **method** (which execution lane owns it) and a **next story** (concrete work).

### How to categorize results from a session

1. **Locate the session:** **`<repo>/.unsubscribe_page_capture/session_<UTC>_<hash>/`** — same base directory as in `PAGE_CAPTURE_DIR` (`unsubscribe_page_capture.py`; typically the checkout root that contains `src/`).
2. **Read** `session_meta.json` for jobs (subject/sender/initial URL).
3. **Aggregate** `manifest.json` — example counts by primary bucket:
   ```bash
   jq '[.snapshots[].primary_category] | group_by(.) | map({category: .[0], n: length})' manifest.json
   ```
4. **Sub-cluster** within a bucket by **host** (first party vs ESP) and **evidence_tags**:
   ```bash
   jq -r '.snapshots[] | [.step, .primary_category, .page_url, (.evidence_tags|join("|"))] | @tsv' manifest.json
   ```
5. **Treat `after_flow_complete` vs `after_navigate`** for the same job: if **category** or **host** changes across steps, the flow is a **funnel** (multi-page); plan multi-step handling, not a single click.

**Note:** Agent/cannot read your local capture directory unless paths are under the repo or pasted. Refresh this table with **real counts** from your `jq` output when triaging.

### Method legend (execution lanes)

| Method | Meaning |
| ------ | ------- |
| **M1 — RFC 8058** | `try_one_click_unsubscribe` (header POST); report `server-acknowledged`; no browser. |
| **M2 — body URL + browser** | `extract_unsubscribe_link` → `batch_browser_unsubscribe` (attach once, sequential URLs). |
| **M3 — browser multi-step** | Extend `_try_click_unsubscribe_on_page`: pre-clicks, second pass, form fill (already partially done). |
| **M4 — env-assisted** | `UNSUBSCRIBE_SUBSCRIBER_EMAIL` and/or future env for known form fields. |
| **M5 — user session** | Brave already logged in; automation stops at blocker with a **clear report line**; user completes manually in the open profile. |
| **M6 — out of scope** | Captcha solving / account takeover / server-side fetch of untrusted URLs — not automated; document + skip. |

### Case table (stable IDs ↔ manifest category ↔ method ↔ plan)

Each **case** is one row. **Detection** references `unsubscribe_page_capture.categorize_unsubscribe_page` (`UnsubscribePageCategory` + tags). Implementation **extends** markers/selectors/tests as new HTML samples land in captures.

| ID | Manifest `primary_category` | Typical `evidence_tags` / notes | Primary method | Next story (ordered) |
| --- | --- | --- | --- | --- |
| **CAP-01** | `confirmation_likely` | `confirmation_text:*` on `after_flow_complete` (or last step) | **M2/M3** (already navigated); outcome is **confirmed** in report | (1) Add any **new confirmation phrases** from captured HTML into `page_confirmation_markers.py` + unit tests. (2) Prefer **last step** in funnel for confirmation check if earlier steps are forms. |
| **CAP-02** | `preference_center` | `preference_center_text:*`, `mentions_preferences` | **M3** | (1) Expand `_UNSUBSCRIBE_FROM_ALL_NEEDLES` from real copy (i18n, “all emails”). (2) Handle **Submit / Save** after radio choice where no “Unsubscribe” literal. (3) Snapshot tests from anonymized HTML fixtures per host **cluster**. |
| **CAP-03** | `email_entry` | `email_type_input` | **M3 + M4** | (1) Ensure fill runs **before** primary click; optional **Confirm email** second field. (2) Detect `input[type=text]` with `name=*email*` if ESP omits `type=email`. (3) Fixture tests per pattern. |
| **CAP-04** | `generic_unsubscribe_context` | `mentions_unsubscribe` / `mentions_opt_out` but no confirmation/preference text match | **M2/M3** | (1) Broaden `_find_unsubscribe_element` + JS needle list from captured pages. (2) **Cluster by registrable domain** in manifest; add host-specific rules only when generic fails (avoid one-off sprawl: one policy module per **domain cluster**). |
| **CAP-05** | `captcha_or_bot_check` | `captcha_like` | **M6** detect → **M5** complete | (1) On detect: stop automated clicks for that URL, **report** “captcha — complete in Brave”. (2) Optional: pause with message; do not attempt third-party solving. |
| **CAP-06** | `login_or_auth` | `login_like` | **M5** | (1) Report “login required — use logged-in Brave profile”. (2) Do not inject passwords. (3) If Same SSO opens, document “open session first” in README. |
| **CAP-07** | `error_or_blocker` | `error_like` | **M5** / manual | (1) Split **expired token** vs **404** vs **rate limit** using copy + status (future: HTTP if feasible). (2) Suggest user re-open fresh link from Gmail. |
| **CAP-08** | `unknown` | weak/no tags | **Triage** | (1) Re-run categorizer with longer `text_preview` or full HTML classifiers. (2) Assign to CAP-02–CAP-04 once manually labeled; add **golden HTML** fixture. |

### Funnel / multi-step (cross-cutting)

| ID | Pattern | Method | Plan |
| --- | --- | --- | --- |
| **CAP-F1** | Same job: `after_navigate` = preference/generic → `after_flow_complete` = confirmation | **M3** | Treat as **single story**: state machine **land → optional pref-click → optional email → click → optional confirm click**; manifest already gives step boundaries **—** align automation and **confirmed** detection with **final** page only (or explicit success page detector). |
| **CAP-F2** | New tab / redirect chain (`page_url` host changes 2+ times) | **M2/M3** | Log **redirect chain** in manifest (optional future field); test **window** focus (already partial). |

### Workflow for maintainers after each field capture

1. Copy or reference `manifest.json` + 1–2 anonymized `.html` samples into `tests/fixtures/capture/` (new) **or** paste `jq` summary into a PR.
2. Update **CAP-*** rows if a **new pattern** appears (new primary bucket or tag).
3. Implement **next story** for the highest-volume bucket first; **TDD**: fixture HTML → failing test → handler change.

---

## Watch-outs

- **Security:** Unsubscribe links are **attacker-controlled**; prefer
**RFC 8058** from headers over scraping arbitrary body links; use
**allowlists** / **block private IPs** if you ever fetch URLs server-side.
- **Product variance:** Some senders omit one-click; some break spec; **e2e**
is explicitly **last resort**.
- **Rate limits:** Batch and backoff Gmail API calls; don't parallelize
unbounded unsubscribe POSTs without care.
- **Personal data:** Logs must not dump full message bodies by default.
- **Browser profile:** Only the user's **Brave** with their real Google login
is source of truth for logged-in sessions. Never use an IDE embedded browser
to judge whether a flow works.
- **Deferred discovery:** A **post–Iteration-6** slice may add a second Gmail pass (bulk-looking messages **without** `List-Unsubscribe` → fetch HTML → body-link detection → classifier with `has_body_unsubscribe_link=True`). Until then, shortlist discovery stays header-driven only.

