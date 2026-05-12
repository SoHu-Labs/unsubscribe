"""Optional failure traces to disk (``enabled=`` on :func:`save_live_brave_failure_trace`)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from unsubscribe import live_brave_trace as lbt


def test_save_live_brave_failure_trace_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR", str(tmp_path))
    driver = MagicMock()
    driver.page_source = "<html></html>"
    lbt.save_live_brave_failure_trace(driver, label="x", error="boom", enabled=False)
    assert list(tmp_path.iterdir()) == []


def test_save_live_brave_failure_trace_skips_when_error_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR", str(tmp_path))
    driver = MagicMock()
    driver.page_source = "<html></html>"
    lbt.save_live_brave_failure_trace(driver, label="x", error="   ", enabled=True)
    lbt.save_live_brave_failure_trace(driver, label="x", error=None, enabled=True)
    assert list(tmp_path.iterdir()) == []


def test_save_live_brave_failure_trace_writes_html_and_error_txt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("UNSUBSCRIBE_LIVE_BRAVE_TRACE_DIR", str(tmp_path))
    driver = MagicMock()
    driver.page_source = "<html><body>x</body></html>"
    lbt.save_live_brave_failure_trace(
        driver,
        label="host_abc",
        error="UnsubscribeElementNotFoundError: n",
        enabled=True,
    )
    html = list(tmp_path.glob("unsubscribe_host_abc_*.html"))
    errf = list(tmp_path.glob("unsubscribe_host_abc_*.error.txt"))
    assert len(html) == 1
    assert len(errf) == 1
    assert "UnsubscribeElementNotFoundError" in errf[0].read_text(encoding="utf-8")


def test_cleanup_unsubscribe_trace_png_removes_unsubscribe_prefix_pngs(
    tmp_path: Path,
) -> None:
    matched = tmp_path / "unsubscribe_a_1.png"
    other = tmp_path / "other.png"
    matched.write_bytes(b"x")
    other.write_bytes(b"x")
    n = lbt.cleanup_unsubscribe_trace_png_files(tmp_path)
    assert n == 1
    assert not matched.exists()
    assert other.exists()
