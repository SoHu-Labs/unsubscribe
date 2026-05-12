"""Extra failure dumps under ``~/Downloads`` when enabled by the caller (default: on).

These are **only** useful paired with a **programmatic error string** you can grep in logs
or page-capture manifests, then open the matching ``.html`` for full DOM context.

``.unsubscribe_page_capture/session_*`` already records ``after_exception`` with ``error`` + HTML;
this module is optional duplication to a directory you choose (default Downloads).

``batch_browser_unsubscribe(..., mirror_failure_trace=True)`` passes that toggle here.

Writes **only** when ``enabled`` is true **and** ``error`` is non-empty after strip:

* ``unsubscribe_{label}_{utc}.html`` — DOM snapshot
* ``unsubscribe_{label}_{utc}.error.txt`` — same text you pass in (exception / failure detail)

No PNG here: raster captures live only under ``UNSUBSCRIBE_PAGE_CAPTURE_SCREENSHOTS`` (see README).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from selenium.webdriver.remote.webdriver import WebDriver

_ENV_TRACE_DIR = "UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR"


def live_brave_trace_dir() -> Path:
    raw = (os.environ.get(_ENV_TRACE_DIR) or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / "Downloads"


def save_live_brave_failure_trace(
    driver: WebDriver,
    *,
    label: str,
    error: str | None = None,
    enabled: bool = True,
) -> None:
    """Write HTML + ``.error.txt`` when ``enabled`` and ``error`` is non-empty after strip."""

    if not enabled:
        return
    err_txt = (error or "").strip()
    if not err_txt:
        return

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:80]
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = live_brave_trace_dir()
    base.mkdir(parents=True, exist_ok=True)
    stem = f"unsubscribe_{safe}_{ts}"
    html_path = base / f"{stem}.html"
    html_path.write_text(driver.page_source or "", encoding="utf-8")
    (base / f"{stem}.error.txt").write_text(err_txt[:8000] + "\n", encoding="utf-8")


def cleanup_unsubscribe_trace_png_files(trace_dir: Path | None = None) -> int:
    """Remove ``unsubscribe_*.png`` from the trace directory (legacy / no longer written)."""

    base = trace_dir if trace_dir is not None else live_brave_trace_dir()
    n = 0
    for p in base.glob("unsubscribe_*.png"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return n
