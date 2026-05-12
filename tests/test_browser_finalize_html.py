"""Post-batch browser result finalization from saved capture HTML."""

from __future__ import annotations

import json
from pathlib import Path

from unsubscribe.browser_unsubscribe import _finalize_browser_results_from_saved_html
from unsubscribe.unsubscribe_page_capture import PageCaptureSession


def _session_dir_with_snapshots(
    tmp_path: Path,
    *,
    job_batch_index: int,
    html_name: str,
    html_body: str,
    sequences: list[int],
) -> Path:
    d = tmp_path / "sess"
    d.mkdir()
    (d / html_name).write_text(html_body, encoding="utf-8")
    snaps = []
    for seq in sequences:
        snaps.append(
            {
                "sequence": seq,
                "job_batch_index": job_batch_index,
                "files": {"html": html_name},
            }
        )
    (d / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "snapshots": snaps}),
        encoding="utf-8",
    )
    return d


def test_finalize_upgrades_from_html_confirmation(tmp_path: Path) -> None:
    d = _session_dir_with_snapshots(
        tmp_path,
        job_batch_index=1,
        html_name="last.html",
        html_body="<html><body>You've been unsubscribed</body></html>",
        sequences=[1, 2],
    )
    session = PageCaptureSession.__new__(PageCaptureSession)
    session.session_dir = d
    results: list[dict] = [
        {
            "method": "browser",
            "status": "clicked-no-confirmation",
            "detail": "provisional",
        }
    ]
    jobs = [(1, "s", "snd", "https://x.example/u", None)]
    _finalize_browser_results_from_saved_html(results, jobs, session)
    assert results[0]["status"] == "confirmed"
    assert "saved page HTML" in results[0]["detail"]


def test_finalize_downgrades_when_html_lacks_confirmation(tmp_path: Path) -> None:
    d = _session_dir_with_snapshots(
        tmp_path,
        job_batch_index=1,
        html_name="last.html",
        html_body="<html><body>Manage subscription</body></html>",
        sequences=[1],
    )
    session = PageCaptureSession.__new__(PageCaptureSession)
    session.session_dir = d
    results: list[dict] = [
        {
            "method": "browser",
            "status": "confirmed",
            "detail": "browser → live said yes",
        }
    ]
    jobs = [(1, "s", "snd", "https://x.example/u", None)]
    _finalize_browser_results_from_saved_html(results, jobs, session)
    assert results[0]["status"] == "clicked-no-confirmation"


def test_finalize_failed_appends_when_html_shows_confirmation(tmp_path: Path) -> None:
    d = _session_dir_with_snapshots(
        tmp_path,
        job_batch_index=1,
        html_name="x.html",
        html_body="<p>Successfully unsubscribed</p>",
        sequences=[3],
    )
    session = PageCaptureSession.__new__(PageCaptureSession)
    session.session_dir = d
    results: list[dict] = [
        {
            "method": "browser",
            "status": "failed",
            "detail": "browser → ✗ failed: timeout",
        }
    ]
    jobs = [(1, "s", "snd", "https://x.example/u", None)]
    _finalize_browser_results_from_saved_html(results, jobs, session)
    assert results[0]["status"] == "failed"
    assert "confirmation-like wording" in results[0]["detail"]
