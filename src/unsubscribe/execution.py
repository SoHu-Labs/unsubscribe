"""After interactive check: one-click POST, body link extraction, then browser batch."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import cast
from urllib.parse import urlparse

from unsubscribe.browser_unsubscribe import batch_browser_unsubscribe
from unsubscribe.gmail_facade import GmailFacade, GmailHeaderSummary, headers_from_summary
from unsubscribe.timed_run import TimedRun, format_progress_line
from unsubscribe.unsubscribe_link import NoUnsubscribeLinkError, UnsafeLinkError, extract_unsubscribe_link
from unsubscribe.unsubscribe_oneclick import (
    NoUnsubscribeHeaderError,
    UnsubscribeNotOneClickError,
    UnsubscribePostRedirectError,
    try_one_click_unsubscribe,
)


@dataclass(frozen=True)
class MessageAutomationOutcome:
    """One row in the post-run automation report (one selected message)."""

    message_id: str
    from_header: str
    subject: str
    status: str
    detail: str = ""

    # status values: one_click_ok, browser_ok, browser_failed, browser_skipped,
    # no_automated_path, mailto_only


@dataclass(frozen=True)
class AutomationReport:
    outcomes: tuple[MessageAutomationOutcome, ...]

    @property
    def verified_success_count(self) -> int:
        """Count only outcomes we record as a completed automated step (not skipped, not mailto-only)."""
        return sum(1 for o in self.outcomes if o.status in ("one_click_ok", "browser_ok"))

    def __len__(self) -> int:
        return len(self.outcomes)


_STATUS_HEADLINE: dict[str, str] = {
    "one_click_ok": "[one-click HTTP]",
    "browser_ok": "[browser]",
    "browser_failed": "[browser — no confirmation]",
    "browser_skipped": "[browser — not run]",
    "no_automated_path": "[no automated path]",
    "mailto_only": "[mailto — manual only]",
}


def print_automation_report(report: AutomationReport) -> None:
    """Human-readable report: every selected message, honest outcomes, no inflated totals."""
    print("\nResults by message:")
    for o in report.outcomes:
        head = _STATUS_HEADLINE.get(o.status, f"[{o.status}]")
        print(f"  {head} {o.from_header} — {o.subject}")
        if o.detail:
            wrap = o.detail.replace("\n", " ")
            if len(wrap) > 160:
                wrap = wrap[:157] + "…"
            print(f"           {wrap}")

    v = report.verified_success_count
    n = len(report)
    print(
        f"\nVerified automated completions: {v} of {n} "
        f"(one-click server accepted request, or browser flow reported success). "
        f"Skipped browser steps are not counted."
    )


def debugger_address_from_env() -> str | None:
    raw = (os.environ.get("UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS") or "").strip()
    return raw or None


def _subject_preview(subj: str, max_len: int = 52) -> str:
    s = subj.replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def run_automated_unsubscribe(
    facade: GmailFacade,
    selected: list[GmailHeaderSummary],
    *,
    debugger_address: str | None,
    timeout_per_url_s: float = 30,
    verbose: bool = True,
) -> AutomationReport:
    """
    For each selected message: RFC 8058 one-click first, then allowlisted body link + browser.

    Returns an :class:`AutomationReport` with one row per message (honest ``browser_skipped``
    when debugger is missing — never counted as success).

    With ``verbose=True`` (default), prints progress lines in the same shape as
    ``googleads_invoice.run_month`` (``[n/N] +step/cum msg``).
    """
    n = len(selected)
    if n == 0:
        return AutomationReport(())

    t0 = time.monotonic()
    slots: list[MessageAutomationOutcome | None] = [None] * n
    browser_jobs: list[tuple[int, GmailHeaderSummary, str]] = []

    if verbose:
        print("", flush=True)

    for i, m in enumerate(selected):
        headers = headers_from_summary(m)
        mailto_hint = ""

        try:
            out = try_one_click_unsubscribe(headers)
            if out.startswith("One-Click unsubscribe accepted"):
                slots[i] = MessageAutomationOutcome(
                    m.id,
                    m.from_,
                    m.subject,
                    "one_click_ok",
                    out,
                )
                if verbose:
                    sq = _subject_preview(m.subject)
                    print(
                        f"    [{i + 1}/{n}] {m.from_} — \"{sq}\" — "
                        f"one-click unsubscribe accepted.",
                        flush=True,
                    )
                continue
            low = out.lower()
            if low.startswith("manual action"):
                mailto_hint = out[:300]
        except (
            NoUnsubscribeHeaderError,
            UnsubscribeNotOneClickError,
            UnsubscribePostRedirectError,
        ):
            pass
        except OSError:
            pass
        except Exception:
            pass

        body_url: str | None = None
        extract_err = ""
        try:
            html = facade.get_message_html(m.id)
            body_url = extract_unsubscribe_link(html)
        except (NoUnsubscribeLinkError, UnsafeLinkError) as e:
            extract_err = str(e) or type(e).__name__
        except Exception as e:
            extract_err = str(e) or type(e).__name__

        if not body_url:
            if mailto_hint:
                detail = mailto_hint
                if extract_err:
                    detail = f"{mailto_hint} Body: {extract_err}"
                slots[i] = MessageAutomationOutcome(
                    m.id,
                    m.from_,
                    m.subject,
                    "mailto_only",
                    detail,
                )
                if verbose:
                    sq = _subject_preview(m.subject)
                    print(
                        f"    [{i + 1}/{n}] {m.from_} — \"{sq}\" — "
                        f"mailto / manual only (no automated browser URL).",
                        flush=True,
                    )
            else:
                slots[i] = MessageAutomationOutcome(
                    m.id,
                    m.from_,
                    m.subject,
                    "no_automated_path",
                    extract_err or "No allowlisted unsubscribe link in body.",
                )
                if verbose:
                    sq = _subject_preview(m.subject)
                    ere = (extract_err or "no allowlisted link")[:72]
                    print(
                        f"    [{i + 1}/{n}] {m.from_} — \"{sq}\" — "
                        f"no automated path ({ere}).",
                        flush=True,
                    )
            continue

        browser_jobs.append((i, m, body_url))
        if verbose:
            host = urlparse(body_url).hostname or body_url[:48]
            sq = _subject_preview(m.subject)
            print(
                f"    [{i + 1}/{n}] {m.from_} — \"{sq}\" — "
                f"queued for Brave — {host}.",
                flush=True,
            )

    elapsed_analysis = time.monotonic() - t0
    nb = len(browser_jobs)

    if not browser_jobs:
        if verbose:
            all_one_click = all(
                s is not None and s.status == "one_click_ok" for s in slots
            )
            if all_one_click:
                tail = (
                    "Done. Brave not used — every selection completed via "
                    "List-Unsubscribe one-click POST (no browser URLs queued)."
                )
            else:
                tail = (
                    "Done. Brave not used — no browser URLs were queued "
                    "(mailto-only, no path, or one-click without a follow-up link; see lines above)."
                )
            print(
                format_progress_line(
                    1, 1, elapsed_analysis, elapsed_analysis, tail
                ),
                flush=True,
            )
        assert all(x is not None for x in slots)
        return AutomationReport(cast(tuple[MessageAutomationOutcome, ...], tuple(slots)))

    if not debugger_address:
        total_steps = 2
    else:
        total_steps = 1 + 2 + 2 * nb

    tr = TimedRun(total_steps, enabled=verbose)
    tr.t0 = t0
    tr.last = time.monotonic()
    tr.n = 2

    if verbose:
        if debugger_address:
            tail = (
                f"Message analysis complete; {nb} URL(s) queued for Brave "
                f"(attach with UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS, e.g. 127.0.0.1:9222)."
            )
        else:
            tail = (
                f"Message analysis complete; {nb} URL(s) need Brave but "
                f"UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS is unset (browser phase will be skipped)."
            )
        print(
            format_progress_line(
                1, total_steps, elapsed_analysis, elapsed_analysis, tail
            ),
            flush=True,
        )

    if not debugger_address:
        for i, m, url in browser_jobs:
            slots[i] = MessageAutomationOutcome(
                m.id,
                m.from_,
                m.subject,
                "browser_skipped",
                "Set UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS and start Brave with "
                f"--remote-debugging-port to open: {url}",
            )
        tr.step(
            f"Browser automation skipped — set UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS and "
            f"start Brave with --remote-debugging-port ({nb} URL(s) not opened). "
            "Brave was not contacted."
        )
    else:
        urls = [u for _, _, u in browser_jobs]
        browser_results = batch_browser_unsubscribe(
            urls,
            debugger_address=debugger_address,
            timeout_per_url_s=timeout_per_url_s,
            progress=tr,
        )

        for i, m, url in browser_jobs:
            ok = bool(browser_results.get(url))
            slots[i] = MessageAutomationOutcome(
                m.id,
                m.from_,
                m.subject,
                "browser_ok" if ok else "browser_failed",
                url,
            )

    assert all(x is not None for x in slots)
    return AutomationReport(cast(tuple[MessageAutomationOutcome, ...], tuple(slots)))
