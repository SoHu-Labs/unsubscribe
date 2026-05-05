"""Batch open unsubscribe URLs in an attached Brave session and click through."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from unsubscribe.browser_helpers import chrome_driver_attach
from unsubscribe.live_brave_trace import save_live_brave_trace
from unsubscribe.page_confirmation_markers import (
    CONFIRMATION_TEXT_MARKERS,
    PREFERENCE_CENTER_SNIPPETS,
)
from unsubscribe.timed_run import TimedRun
from unsubscribe.unsubscribe_page_capture import PageCaptureSession

logger = logging.getLogger(__name__)

# Jobs: ``(email_index, subject, sender_display, url)`` — ``email_index`` may be ``None``.
BrowserUnsubscribeJob = tuple[int | None, str, str, str]


class UnsubscribeFlowCase:
    """Page shapes the automation tries to handle (each has dedicated tests).

    * **SIMPLE_SINGLE_CLICK** — one primary unsubscribe / opt-out control.
    * **UNSUBSCRIBE_FROM_ALL_THEN_CLICK** — preference center: choose “unsubscribe from all” (or
      similar) then click Unsubscribe / Submit (handled via pre-clicks + second pass).
    * **EMAIL_FIELD_THEN_CLICK** — form shows an email field; set ``subscriber_email`` (or
      ``UNSUBSCRIBE_SUBSCRIBER_EMAIL`` from execution) before the main click.
    """

    SIMPLE_SINGLE_CLICK = "simple_single_click"
    UNSUBSCRIBE_FROM_ALL_THEN_CLICK = "unsubscribe_from_all_then_unsubscribe"
    EMAIL_FIELD_THEN_CLICK = "email_field_then_unsubscribe"


class UnsubscribeElementNotFoundError(RuntimeError):
    """No clickable unsubscribe control matched on the page."""


_UNSUBSCRIBED_PAGE_MARKERS: tuple[str, ...] = CONFIRMATION_TEXT_MARKERS

# Needles passed into in-page script (same as preference-center snippets).
_UNSUBSCRIBE_FROM_ALL_NEEDLES: tuple[str, ...] = PREFERENCE_CENTER_SNIPPETS


def _visible_page_text(driver: WebDriver) -> str:
    try:
        return str(
            driver.execute_script(
                "return document.body && document.body.innerText || ''"
            )
            or ""
        )
    except Exception:
        return ""


def _page_suggests_unsubscribed_confirmed(driver: WebDriver) -> bool:
    low = _visible_page_text(driver).lower()
    return any(m in low for m in _UNSUBSCRIBED_PAGE_MARKERS)


def _maybe_click_unsubscribe_from_all(driver: WebDriver) -> bool:
    """If the page offers “unsubscribe from all”, click the first visible match."""
    script = """
    const needles = arguments[0];
    function visible(e) {
      if (!e || !e.getBoundingClientRect) return false;
      const r = e.getBoundingClientRect();
      if (r.width < 1 && r.height < 1) return false;
      const st = window.getComputedStyle(e);
      if (st.visibility === 'hidden' || st.display === 'none') return false;
      return true;
    }
    function textish(el) {
      let t = (el.innerText || el.textContent || el.value ||
        el.getAttribute('aria-label') || '').toLowerCase();
      if (el.labels && el.labels.length) {
        for (const lb of el.labels) {
          t += ' ' + (lb.innerText || '').toLowerCase();
        }
      }
      return t;
    }
    const sel = 'button, a, label, [role="button"], input[type="radio"], input[type="checkbox"]';
    for (const el of document.querySelectorAll(sel)) {
      if (!visible(el)) continue;
      const t = textish(el);
      for (const n of needles) {
        if (t.includes(String(n).toLowerCase())) {
          el.click();
          return true;
        }
      }
    }
    return false;
    """
    try:
        return bool(driver.execute_script(script, list(_UNSUBSCRIBE_FROM_ALL_NEEDLES)))
    except Exception:
        return False


def _maybe_fill_visible_email_field(driver: WebDriver, email: str) -> bool:
    """Fill the first visible, empty email-like input (preference centers)."""
    raw = (email or "").strip()
    if not raw:
        return False
    selectors = (
        'input[type="email"]',
        'input[name*="email"]',
        'input[id*="email"]',
        'input[placeholder*="email"]',
        'input[placeholder*="Email"]',
    )
    for sel in selectors:
        try:
            for inp in driver.find_elements(By.CSS_SELECTOR, sel):
                try:
                    if not inp.is_displayed():
                        continue
                    if (inp.get_attribute("value") or "").strip():
                        continue
                    inp.clear()
                    inp.send_keys(raw)
                    return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def _find_unsubscribe_element(driver: WebDriver) -> WebElement:
    """Try strategies to find an unsubscribe control (visible)."""
    selectors: list[str] = [
        '//a[contains(text(), "Unsubscribe")]',
        '//button[contains(text(), "Unsubscribe")]',
        '//a[contains(text(), "unsubscribe")]',
        '//button[contains(text(), "unsubscribe")]',
        '//a[contains(text(), "Opt out")]',
        '//button[contains(text(), "Opt out")]',
        '//a[contains(text(), "opt-out")]',
        '//a[contains(text(), "Manage preferences")]',
        '//button[contains(text(), "Manage preferences")]',
        '//*[contains(@aria-label, "Unsubscribe")]',
        '//*[contains(@aria-label, "unsubscribe")]',
        '//*[contains(@aria-label, "Opt out")]',
        '//*[contains(@aria-label, "opt-out")]',
        '//*[contains(@aria-label, "Manage preferences")]',
        '//*[@role="button" and contains(@aria-label, "Unsubscribe")]',
        '//*[contains(text(), "Confirm unsubscribe")]',
        '//*[contains(text(), "Yes, unsubscribe me")]',
    ]
    for xpath in selectors:
        elements = driver.find_elements(By.XPATH, xpath)
        visible = [el for el in elements if el.is_displayed()]
        if visible:
            return visible[0]
    js_code = r"""
    const needles = [
        'unsubscribe', 'opt out', 'opt-out', 'manage preferences',
        'confirm unsubscribe', 'yes, unsubscribe me',
    ];
    let els = document.querySelectorAll('a, button, span, div, [role="button"]');
    for (let el of els) {
        const t = (el.textContent || '').trim().toLowerCase();
        for (const n of needles) {
            if (t.includes(n)) { return el; }
        }
    }
    return null;
    """
    result = driver.execute_script(js_code)
    if result is not None:
        return result
    raise UnsubscribeElementNotFoundError("No unsubscribe control found on the page.")


def _url_trace_label(url: str) -> str:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    try:
        host = urlparse(url).hostname or "nohost"
    except Exception:
        host = "badurl"
    return f"{host}_{h}"


def _page_ready(driver: WebDriver) -> bool:
    try:
        return driver.execute_script("return document.readyState") == "complete"
    except Exception:
        return False


def _click_unsubscribe_once_main_or_iframes(driver: WebDriver) -> None:
    """One attempt: primary Unsubscribe control in main document or first matching iframe."""
    try:
        el = _find_unsubscribe_element(driver)
        el.click()
        return
    except UnsubscribeElementNotFoundError:
        pass

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for fr in frames:
        try:
            driver.switch_to.frame(fr)
            el = _find_unsubscribe_element(driver)
            el.click()
            driver.switch_to.default_content()
            return
        except Exception:
            driver.switch_to.default_content()
    raise UnsubscribeElementNotFoundError(
        "No unsubscribe control found (main document or iframes)."
    )


def _try_click_unsubscribe_on_page(
    driver: WebDriver,
    *,
    settle_s: float = 2.0,
    subscriber_email: str | None = None,
    record_step: Callable[[str], None] | None = None,
) -> None:
    """Preference-center pre-steps, then unsubscribe click (second pass if no confirmation).

    ``record_step`` receives logical step names for optional page capture (see ``unsubscribe_page_capture``).
    """

    def _r(name: str) -> None:
        if record_step is not None:
            record_step(name)

    driver.switch_to.default_content()
    WebDriverWait(driver, 15).until(_page_ready)
    time.sleep(min(settle_s, 3.0))
    _r("after_landing_settled")

    _maybe_click_unsubscribe_from_all(driver)
    time.sleep(0.45)
    _r("after_maybe_unsubscribe_from_all_click")

    filled = (
        bool(subscriber_email)
        and _maybe_fill_visible_email_field(driver, subscriber_email or "")
    )
    if filled:
        time.sleep(0.35)
        _r("after_email_field_fill")

    _click_unsubscribe_once_main_or_iframes(driver)
    _r("after_primary_unsubscribe_click")
    time.sleep(min(1.5, settle_s))
    if _page_suggests_unsubscribed_confirmed(driver):
        return
    try:
        driver.switch_to.default_content()
        _click_unsubscribe_once_main_or_iframes(driver)
        _r("after_secondary_unsubscribe_click")
    except UnsubscribeElementNotFoundError:
        pass


def _result_row(
    email_index: int | None,
    subject: str,
    sender: str,
    *,
    method: str,
    status: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "email_index": email_index,
        "subject": subject,
        "sender": sender,
        "method": method,
        "status": status,
        "detail": detail,
    }


def batch_browser_unsubscribe(
    jobs: list[BrowserUnsubscribeJob],
    *,
    debugger_address: str,
    timeout_per_url_s: float = 30,
    subscriber_email: str | None = None,
    progress: TimedRun | None = None,
    quiet: bool = False,
) -> list[dict[str, Any]]:
    """
    Attach **once**, visit each URL in order, try to click an unsubscribe control.

    Each job is ``(email_index, subject, sender, url)``. Returns one result dict per job,
    with ``status`` in ``confirmed`` / ``clicked-no-confirmation`` / ``failed``.

    ``subscriber_email`` fills visible empty email inputs on preference-center pages
    (see ``UnsubscribeFlowCase.EMAIL_FIELD_THEN_CLICK``).
    """
    if not jobs:
        return []

    urls = [j[3] for j in jobs]

    if progress is None:
        progress = TimedRun(2 + 2 * len(urls), enabled=not quiet)

    progress.step(
        f"Attaching WebDriver to Brave at {debugger_address} (already running with "
        "--remote-debugging-port)..."
    )
    driver: WebDriver | None = None
    results: list[dict[str, Any]] = []
    capture_session: PageCaptureSession | None = PageCaptureSession.create(jobs)
    if not quiet:
        progress.step(
            f"Recording pages for format learning to {capture_session.session_dir}…"
        )
    try:
        driver = chrome_driver_attach(debugger_address=debugger_address)
        for idx, (email_index, subject, sender, url) in enumerate(jobs, start=1):
            host = urlparse(url).hostname or url[:48]
            job_row: BrowserUnsubscribeJob = (email_index, subject, sender, url)

            def _record_step(
                step: str,
                *,
                _idx: int = idx,
                _url: str = url,
                _job: BrowserUnsubscribeJob = job_row,
            ) -> None:
                if capture_session is not None and driver is not None:
                    capture_session.record_snapshot(
                        driver,
                        job_batch_index=_idx,
                        step=step,
                        initial_url=_url,
                        job=_job,
                    )

            try:
                progress.step(
                    f"Opening unsubscribe URL {idx}/{len(jobs)} in browser — {host} ..."
                )
                driver.get(url)
                try:
                    handles = driver.window_handles
                    if len(handles) > 1:
                        driver.switch_to.window(handles[-1])
                except Exception:
                    pass

                if capture_session is not None:
                    capture_session.record_snapshot(
                        driver,
                        job_batch_index=idx,
                        step="after_navigate",
                        initial_url=url,
                        job=job_row,
                    )

                _try_click_unsubscribe_on_page(
                    driver,
                    settle_s=min(2.0, timeout_per_url_s / 4),
                    subscriber_email=subscriber_email,
                    record_step=_record_step,
                )
                time.sleep(min(1.5, timeout_per_url_s / 6))
                if capture_session is not None:
                    capture_session.record_snapshot(
                        driver,
                        job_batch_index=idx,
                        step="after_flow_complete",
                        initial_url=url,
                        job=job_row,
                    )
                if _page_suggests_unsubscribed_confirmed(driver):
                    results.append(
                        _result_row(
                            email_index,
                            subject,
                            sender,
                            method="browser",
                            status="confirmed",
                            detail=(
                                'browser → button clicked → "unsubscribed" seen on page ✓'
                            ),
                        )
                    )
                else:
                    results.append(
                        _result_row(
                            email_index,
                            subject,
                            sender,
                            method="browser",
                            status="clicked-no-confirmation",
                            detail=(
                                "browser → button clicked → no clear unsubscribe confirmation "
                                "on page (check inbox or the site)"
                            ),
                        )
                    )
                progress.step(
                    f"Unsubscribe action {idx}/{len(jobs)} ({host}) — finished."
                )
            except Exception as exc:
                logger.warning("Unsubscribe failed for %s: %s", url, exc)
                if capture_session is not None and driver is not None:
                    try:
                        capture_session.record_snapshot(
                            driver,
                            job_batch_index=idx,
                            step="after_exception",
                            initial_url=url,
                            job=job_row,
                            error=str(exc)[:800],
                        )
                    except Exception:
                        pass
                msg = str(exc) or type(exc).__name__
                results.append(
                    _result_row(
                        email_index,
                        subject,
                        sender,
                        method="browser",
                        status="failed",
                        detail=f"browser → ✗ failed: {msg}",
                    )
                )
                progress.step(
                    f"Unsubscribe action {idx}/{len(jobs)} ({host}) — failed."
                )
                try:
                    save_live_brave_trace(driver, label=_url_trace_label(url))
                except Exception as trace_exc:
                    logger.warning("Could not save trace: %s", trace_exc)
                continue
    finally:
        if driver is not None:
            progress.step("Closing WebDriver session (your Brave window stays open).")
            try:
                driver.quit()
            except Exception as e:
                logger.warning("driver.quit() failed: %s", e)

    return results
