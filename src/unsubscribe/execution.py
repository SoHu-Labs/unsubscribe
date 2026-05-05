"""After interactive check: one-click POST, body link extraction, then browser batch."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import cast

from unsubscribe.browser_unsubscribe import batch_browser_unsubscribe
from unsubscribe.gmail_facade import GmailFacade, GmailHeaderSummary, headers_from_summary
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
    print("\nAutomated unsubscribe — per message:")
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


def run_automated_unsubscribe(
    facade: GmailFacade,
    selected: list[GmailHeaderSummary],
    *,
    debugger_address: str | None,
    timeout_per_url_s: float = 30,
) -> AutomationReport:
    """
    For each selected message: RFC 8058 one-click first, then allowlisted body link + browser.

    Returns an :class:`AutomationReport` with one row per message (honest ``browser_skipped``
    when debugger is missing — never counted as success).
    """
    n = len(selected)
    if n == 0:
        return AutomationReport(())

    slots: list[MessageAutomationOutcome | None] = [None] * n
    browser_jobs: list[tuple[int, GmailHeaderSummary, str]] = []

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
            else:
                slots[i] = MessageAutomationOutcome(
                    m.id,
                    m.from_,
                    m.subject,
                    "no_automated_path",
                    extract_err or "No allowlisted unsubscribe link in body.",
                )
            continue

        browser_jobs.append((i, m, body_url))

    if browser_jobs:
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
        else:
            urls = [u for _, _, u in browser_jobs]
            browser_results = batch_browser_unsubscribe(
                urls,
                debugger_address=debugger_address,
                timeout_per_url_s=timeout_per_url_s,
            )
            print()
            print("Browser batch (by URL):")
            for url, ok in browser_results.items():
                tag = "ok" if ok else "fail"
                print(f"  [{tag}] {url}")
            br_ok = sum(1 for u in urls if browser_results.get(u))
            print(f"  URLs reported success: {br_ok} of {len(urls)}.")

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
