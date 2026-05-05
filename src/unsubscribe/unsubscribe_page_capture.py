"""Record and categorize unsubscribe landing pages for format learning.

Sessions are created **whenever** ``batch_browser_unsubscribe`` runs — the same moment you already
attach to Brave via ``UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS`` (no extra env toggle).

Tune behavior with **module constants** below (``PAGE_CAPTURE_DIR``, ``PAGE_CAPTURE_SCREENSHOTS``,
``PAGE_CAPTURE_WAIT_S``, ``PAGE_CAPTURE_MIN_VISIBLE_CHARS``).

Each snapshot writes:

* ``*.html`` — best available DOM snapshot (``page_source`` vs ``documentElement.outerHTML``, longer wins).
* ``*.visible.txt`` — full ``document.body.innerText`` (capped), so SPAs and mobile shells still yield readable content.
* ``manifest.json`` includes a short excerpt; use ``.visible.txt`` for full page copy.

Default ``PAGE_CAPTURE_DIR``: next to ``src/`` in this checkout (parent of the ``src`` package directory).
"""

from __future__ import annotations

import json
import hashlib
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from selenium.webdriver.remote.webdriver import WebDriver

from unsubscribe.page_confirmation_markers import (
    CONFIRMATION_TEXT_MARKERS,
    PREFERENCE_CENTER_SNIPPETS,
)

logger = logging.getLogger(__name__)

# One browser job: (email_index, subject, sender_display, url)
BrowserJobRow = tuple[int | None, str, str, str]

# --- Format-learning capture (no env vars): edit here as needed ---
# Directory is the repo root that contains ``src/`` (…/unsubscribe/.unsubscribe_page_capture).
PAGE_CAPTURE_DIR = Path(__file__).resolve().parent.parent.parent / ".unsubscribe_page_capture"
PAGE_CAPTURE_SCREENSHOTS = True
PAGE_CAPTURE_WAIT_S = 12.0
PAGE_CAPTURE_MIN_VISIBLE_CHARS = 80

_MANIFEST_TEXT_EXCERPT = 8000
_VISIBLE_FILE_MAX_CHARS = 500_000
_MIN_HTML_FOR_STATIC_SKIP_WAIT = 6000


class UnsubscribePageCategory:
    """High-level bucket for captured pages (heuristic — for triage, not ground truth)."""

    CAPTCHA_OR_BOT_CHECK = "captcha_or_bot_check"
    LOGIN_OR_AUTH = "login_or_auth"
    ERROR_OR_BLOCKER = "error_or_blocker"
    CONFIRMATION_LIKELY = "confirmation_likely"
    PREFERENCE_CENTER = "preference_center"
    EMAIL_ENTRY = "email_entry"
    GENERIC_UNSUBSCRIBE_CONTEXT = "generic_unsubscribe_context"
    UNKNOWN = "unknown"


def _visible_inner_text_raw(driver: WebDriver) -> str:
    try:
        return str(
            driver.execute_script(
                "return document.body && document.body.innerText || ''"
            )
            or ""
        )
    except Exception:
        return ""


def _wait_for_capture_ready(driver: WebDriver) -> None:
    """Give SPAs / redirects time to paint real copy before reading DOM."""
    timeout_s = max(0.0, float(PAGE_CAPTURE_WAIT_S))
    min_len = max(0, int(PAGE_CAPTURE_MIN_VISIBLE_CHARS))
    if timeout_s <= 0:
        return
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            inner = _visible_inner_text_raw(driver)
            if len(inner.strip()) >= min_len:
                return
            ps = len(driver.page_source or "")
            if ps >= _MIN_HTML_FOR_STATIC_SKIP_WAIT:
                return
        except Exception:
            pass
        time.sleep(0.25)


def _html_snapshot_best_effort(driver: WebDriver) -> str:
    """Prefer the longer of Selenium page_source vs document outerHTML (some shells differ)."""
    src = ""
    try:
        src = driver.page_source or ""
    except Exception:
        src = ""
    outer = ""
    try:
        outer = str(
            driver.execute_script(
                "return document.documentElement && document.documentElement.outerHTML || ''"
            )
            or ""
        )
    except Exception:
        outer = ""
    if len(outer) > len(src):
        return outer
    return src


def _text_preview(driver: WebDriver, max_chars: int = 6000) -> str:
    raw = _visible_inner_text_raw(driver)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:max_chars] if len(raw) > max_chars else raw


def _title(driver: WebDriver) -> str:
    try:
        return str(driver.title or "")
    except Exception:
        return ""


def _current_url(driver: WebDriver) -> str:
    try:
        return str(driver.current_url or "")
    except Exception:
        return ""


def _html_excerpt(driver: WebDriver, max_chars: int = 12000) -> str:
    src = _html_snapshot_best_effort(driver)
    return src[:max_chars] if len(src) > max_chars else src


def categorize_unsubscribe_page(
    *,
    page_url: str,
    page_title: str,
    text_preview: str,
    html_excerpt: str = "",
) -> tuple[str, list[str]]:
    """
    Assign a **primary** category and a stable list of **evidence** tags.

    Tags are lowercase tokens; the manifest stores both for clustering and future handlers.
    """
    blob = f"{page_title}\n{text_preview}".lower()
    html_low = html_excerpt.lower()

    tags: list[str] = []

    def tag(name: str) -> None:
        if name not in tags:
            tags.append(name)

    if any(
        x in blob or x in html_low
        for x in ("recaptcha", "hcaptcha", "g-recaptcha", "cf-turnstile", "turnstile")
    ):
        tag("captcha_like")

    if any(
        x in blob
        for x in (
            "sign in",
            "log in",
            "log-in",
            "signin",
            "login",
            "password",
            "forgot password",
            "authenticate",
            "oauth",
        )
    ):
        tag("login_like")

    if any(
        x in blob
        for x in (
            "access denied",
            "access blocked",
            "403",
            "404",
            "not found",
            "page not found",
            "something went wrong",
            "try again later",
            "invalid link",
            "expired",
        )
    ):
        tag("error_like")

    for m in CONFIRMATION_TEXT_MARKERS:
        if m in blob:
            tag(f"confirmation_text:{m[:48]}")
            break

    for m in PREFERENCE_CENTER_SNIPPETS:
        if m in blob:
            tag(f"preference_center_text:{m[:48]}")
            break

    if 'type="email"' in html_low or "type='email'" in html_low:
        tag("email_type_input")

    if "unsubscribe" in blob or "unsubscribe" in html_low:
        tag("mentions_unsubscribe")

    if "opt out" in blob or "opt-out" in blob:
        tag("mentions_opt_out")

    if "preferences" in blob or "communication preferences" in blob:
        tag("mentions_preferences")

    primary = UnsubscribePageCategory.UNKNOWN
    if "captcha_like" in tags:
        primary = UnsubscribePageCategory.CAPTCHA_OR_BOT_CHECK
    elif "login_like" in tags:
        primary = UnsubscribePageCategory.LOGIN_OR_AUTH
    elif "error_like" in tags:
        primary = UnsubscribePageCategory.ERROR_OR_BLOCKER
    elif any(t.startswith("confirmation_text:") for t in tags):
        primary = UnsubscribePageCategory.CONFIRMATION_LIKELY
    elif any(t.startswith("preference_center_text:") for t in tags) or "mentions_preferences" in tags:
        primary = UnsubscribePageCategory.PREFERENCE_CENTER
    elif "email_type_input" in tags:
        primary = UnsubscribePageCategory.EMAIL_ENTRY
    elif "mentions_unsubscribe" in tags or "mentions_opt_out" in tags:
        primary = UnsubscribePageCategory.GENERIC_UNSUBSCRIBE_CONTEXT

    return primary, tags


@dataclass
class SnapshotRecord:
    sequence: int
    job_batch_index: int
    email_index: int | None
    step: str
    initial_unsub_url: str
    page_url: str
    page_title: str
    primary_category: str
    evidence_tags: list[str]
    text_preview: str
    error: str | None
    quality_note: str | None
    files: dict[str, str]


class PageCaptureSession:
    """Write HTML (+ optional PNG) and a growing ``manifest.json`` under one session dir."""

    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self._seq = 0

    @classmethod
    def create(cls, jobs: list[BrowserJobRow]) -> PageCaptureSession:
        base = PAGE_CAPTURE_DIR
        base.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        h = hashlib.sha256(
            json.dumps([j[3] for j in jobs], sort_keys=True).encode("utf-8")
        ).hexdigest()[:10]
        session_dir = base / f"session_{ts}_{h}"
        session_dir.mkdir(parents=False, exist_ok=False)

        job_rows: list[dict[str, Any]] = []
        for email_index, subject, sender, url in jobs:
            job_rows.append(
                {
                    "email_index": email_index,
                    "subject": subject,
                    "sender": sender,
                    "initial_url": url,
                }
            )

        meta = {
            "schema_version": 1,
            "started_utc": datetime.now(tz=timezone.utc).isoformat(),
            "capture_trigger": "brave_batch",
            "jobs": job_rows,
        }
        (session_dir / "session_meta.json").write_text(
            json.dumps(meta, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest = {"schema_version": 1, "snapshots": []}
        (session_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Unsubscribe page capture session: %s", session_dir)
        return cls(session_dir)

    def record_snapshot(
        self,
        driver: WebDriver,
        *,
        job_batch_index: int,
        step: str,
        initial_url: str,
        job: BrowserJobRow,
        error: str | None = None,
    ) -> None:
        email_index, _subject, _sender, _job_url = job

        self._seq += 1
        safe_step = re.sub(r"[^\w\-]+", "_", step).strip("_")[:60]
        stem = f"{self._seq:03d}_job{job_batch_index}_{safe_step}"

        _wait_for_capture_ready(driver)

        page_url = _current_url(driver)
        title = _title(driver)
        visible_raw = _visible_inner_text_raw(driver)
        visible_for_file = visible_raw[:_VISIBLE_FILE_MAX_CHARS]
        html_full = _html_snapshot_best_effort(driver)
        html_ex = html_full[:12000] if html_full else ""

        norm_for_tags = re.sub(r"\s+", " ", visible_raw).strip()
        text_for_categorize = norm_for_tags[:40000] if norm_for_tags else norm_for_tags
        if not text_for_categorize:
            text_for_categorize = _text_preview(driver, max_chars=8000)

        primary, tags = categorize_unsubscribe_page(
            page_url=page_url,
            page_title=title,
            text_preview=text_for_categorize,
            html_excerpt=html_ex,
        )

        quality_note: str | None = None
        if len(visible_raw.strip()) < 40 and len(html_full) < 500:
            quality_note = (
                "thin_snapshot: low visible text and small HTML "
                f"(increase PAGE_CAPTURE_WAIT_S in unsubscribe_page_capture or check iframes)"
            )

        files: dict[str, str] = {
            "html": f"{stem}.html",
            "visible_text": f"{stem}.visible.txt",
        }
        visible_path = self.session_dir / files["visible_text"]
        try:
            visible_path.write_text(visible_for_file, encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not save visible text %s: %s", visible_path, exc)
            files["visible_text"] = ""

        html_path = self.session_dir / files["html"]
        try:
            html_path.write_text(html_full, encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not save capture HTML %s: %s", html_path, exc)
            files["html"] = ""

        if PAGE_CAPTURE_SCREENSHOTS:
            png_name = f"{stem}.png"
            png_path = self.session_dir / png_name
            try:
                driver.save_screenshot(str(png_path))
                files["png"] = png_name
            except Exception as exc:
                logger.warning("Could not save capture PNG %s: %s", png_path, exc)

        excerpt = norm_for_tags[:_MANIFEST_TEXT_EXCERPT] if norm_for_tags else text_for_categorize[:_MANIFEST_TEXT_EXCERPT]

        rec = SnapshotRecord(
            sequence=self._seq,
            job_batch_index=job_batch_index,
            email_index=email_index,
            step=step,
            initial_unsub_url=initial_url,
            page_url=page_url,
            page_title=title,
            primary_category=primary,
            evidence_tags=tags,
            text_preview=excerpt,
            error=error,
            quality_note=quality_note,
            files=files,
        )

        man_path = self.session_dir / "manifest.json"
        try:
            data = json.loads(man_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"schema_version": 1, "snapshots": []}
        data.setdefault("snapshots", []).append(asdict(rec))
        man_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
