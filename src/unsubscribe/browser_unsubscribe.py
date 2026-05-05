"""Batch open unsubscribe URLs in an attached Brave session and click through."""

from __future__ import annotations

import hashlib
import logging
import time
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait

from unsubscribe.browser_helpers import chrome_driver_attach
from unsubscribe.live_brave_trace import save_live_brave_trace
from unsubscribe.timed_run import TimedRun

logger = logging.getLogger(__name__)


class UnsubscribeElementNotFoundError(RuntimeError):
    """No clickable unsubscribe control matched on the page."""


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


def _try_click_unsubscribe_on_page(
    driver: WebDriver, *, settle_s: float = 2.0
) -> None:
    """Click unsubscribe in main document or in the first matching iframe."""
    driver.switch_to.default_content()
    WebDriverWait(driver, 15).until(_page_ready)
    time.sleep(min(settle_s, 3.0))

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


def batch_browser_unsubscribe(
    urls: list[str],
    *,
    debugger_address: str,
    timeout_per_url_s: float = 30,
    progress: TimedRun | None = None,
    quiet: bool = False,
) -> dict[str, bool]:
    """
    Attach **once**, visit each URL in order, try to click an unsubscribe control,
    **quit once**. On failure, save a trace and continue.

    When ``progress`` is omitted, starts an internal :class:`TimedRun` (silenced with
    ``quiet=True``, for tests). Otherwise uses the shared counter (e.g. from
    :func:`run_automated_unsubscribe`) so step indices stay global.

    Returns mapping ``url -> success``.
    """
    results: dict[str, bool] = {u: False for u in urls}
    if not urls:
        return results

    if progress is None:
        progress = TimedRun(2 + 2 * len(urls), enabled=not quiet)

    progress.step(
        f"Attaching WebDriver to Brave at {debugger_address} (already running with "
        "--remote-debugging-port)..."
    )
    driver: WebDriver | None = None
    try:
        driver = chrome_driver_attach(debugger_address=debugger_address)
        for idx, url in enumerate(urls, start=1):
            try:
                host = urlparse(url).hostname or url[:48]
                progress.step(
                    f"Opening unsubscribe URL {idx}/{len(urls)} in browser — {host} ..."
                )
                driver.get(url)
                try:
                    handles = driver.window_handles
                    if len(handles) > 1:
                        driver.switch_to.window(handles[-1])
                except Exception:
                    pass

                _try_click_unsubscribe_on_page(
                    driver, settle_s=min(2.0, timeout_per_url_s / 4)
                )
                time.sleep(min(1.5, timeout_per_url_s / 6))
                results[url] = True
                progress.step(
                    f"Unsubscribe action {idx}/{len(urls)} ({host}) — finished (click sent, "
                    "page settled)."
                )
            except Exception as exc:
                logger.warning("Unsubscribe failed for %s: %s", url, exc)
                host = urlparse(url).hostname or url[:48]
                progress.step(
                    f"Unsubscribe action {idx}/{len(urls)} ({host}) — failed ({type(exc).__name__})."
                )
                try:
                    save_live_brave_trace(driver, label=_url_trace_label(url))
                except Exception as trace_exc:
                    logger.warning("Could not save trace: %s", trace_exc)
                results[url] = False
                continue
    finally:
        if driver is not None:
            progress.step("Closing WebDriver session (your Brave window stays open).")
            try:
                driver.quit()
            except Exception as e:
                logger.warning("driver.quit() failed: %s", e)

    return results


def print_unsubscribe_report(results: dict[str, bool]) -> None:
    """Print per-URL status and a summary line."""
    for url, ok in results.items():
        tag = "ok" if ok else "fail"
        print(f"  [{tag}] {url}")
    n = len(results)
    okc = sum(1 for v in results.values() if v)
    print(f"Unsubscribed from {okc} of {n} selected.")
