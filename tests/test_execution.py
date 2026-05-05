"""Tests for post-check automated unsubscribe orchestration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from unsubscribe.execution import (
    print_unsubscribe_report,
    run_automated_unsubscribe,
    subscriber_email_for_browser_from_env,
)
from unsubscribe.gmail_facade import GmailFacade, GmailHeaderSummary
from unsubscribe.unsubscribe_link import NoUnsubscribeLinkError
from unsubscribe.unsubscribe_oneclick import UnsubscribeNotOneClickError


def _msg(mid: str, **kw: object) -> GmailHeaderSummary:
    return GmailHeaderSummary(
        id=mid,
        thread_id="t",
        from_=str(kw.get("from_", "A <a@list-manage.com>")),
        subject=str(kw.get("subject", "S")),
        date=str(kw.get("date", "Mon, 1 Jan 2024 00:00:00 +0000")),
        snippet="",
        list_unsubscribe=str(kw.get("list_unsubscribe")) if kw.get("list_unsubscribe") else None,
        list_unsubscribe_post=str(kw.get("list_unsubscribe_post"))
        if kw.get("list_unsubscribe_post")
        else None,
    )


class _B:
    def get_message_html(self, mid: str) -> str:
        return '<html><a href="https://x.us1.list-manage.com/u">Unsubscribe</a></html>'


def test_run_automated_one_click_server_ack_plus_browser_rows() -> None:
    m1 = _msg("1", list_unsubscribe="<https://u.test/x>", list_unsubscribe_post="List-Unsubscribe=One-Click")
    m2 = _msg("2", list_unsubscribe=None)
    facade = GmailFacade(_B())

    browser_row = {
        "email_index": 2,
        "subject": "S",
        "sender": "A <a@list-manage.com>",
        "method": "browser",
        "status": "confirmed",
        "detail": "browser → unsubscribe confirmation seen on page ✓",
    }

    with (
        patch("unsubscribe.execution.try_one_click_unsubscribe") as mock_1c,
        patch("unsubscribe.execution.batch_browser_unsubscribe") as mock_batch,
    ):
        mock_1c.side_effect = [
            "One-Click unsubscribe accepted (HTTP 204).",
            "manual",
        ]
        mock_batch.return_value = [browser_row]

        with patch("unsubscribe.execution.extract_unsubscribe_link", return_value="https://allow.example/u"):
            rows = run_automated_unsubscribe(
                facade,
                [(1, m1), (2, m2)],
                debugger_address="127.0.0.1:9222",
                verbose=False,
            )

    assert len(rows) == 2
    assert rows[0]["method"] == "one-click"
    assert rows[0]["status"] == "server-acknowledged"
    assert rows[1]["status"] == "confirmed"
    mock_batch.assert_called_once()


def test_subscriber_email_for_browser_from_env_strips_and_none_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("UNSUBSCRIBE_SUBSCRIBER_EMAIL", raising=False)
    assert subscriber_email_for_browser_from_env() is None
    monkeypatch.setenv("UNSUBSCRIBE_SUBSCRIBER_EMAIL", "  u@prefs.test  ")
    assert subscriber_email_for_browser_from_env() == "u@prefs.test"


def test_run_automated_passes_subscriber_email_from_env_to_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNSUBSCRIBE_SUBSCRIBER_EMAIL", "me@site.org")
    m1 = _msg("1", list_unsubscribe=None)
    facade = GmailFacade(_B())
    browser_row = {
        "email_index": 1,
        "subject": "S",
        "sender": "A <a@list-manage.com>",
        "method": "browser",
        "status": "confirmed",
        "detail": "ok",
    }
    with (
        patch("unsubscribe.execution.try_one_click_unsubscribe", return_value="nope"),
        patch("unsubscribe.execution.batch_browser_unsubscribe") as mock_batch,
        patch(
            "unsubscribe.execution.extract_unsubscribe_link",
            return_value="https://z.list-manage.com/x",
        ),
    ):
        mock_batch.return_value = [browser_row]
        run_automated_unsubscribe(
            facade,
            [(1, m1)],
            debugger_address="127.0.0.1:9222",
            verbose=False,
        )
    assert mock_batch.call_args.kwargs.get("subscriber_email") == "me@site.org"


def test_run_automated_skips_browser_without_debugger_address(capsys) -> None:
    m = _msg("1", list_unsubscribe=None)
    facade = GmailFacade(_B())

    with (
        patch("unsubscribe.execution.try_one_click_unsubscribe", side_effect=Exception("no")),
        patch("unsubscribe.execution.batch_browser_unsubscribe") as mock_batch,
        patch(
            "unsubscribe.execution.extract_unsubscribe_link",
            return_value="https://z.list-manage.com/x",
        ),
    ):
        rows = run_automated_unsubscribe(
            facade,
            [(9, m)],
            debugger_address=None,
            verbose=False,
        )

    mock_batch.assert_not_called()
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["method"] == "browser"
    assert "GOOGLEADS_BROWSER_DEBUGGER_ADDRESS" in rows[0]["detail"]
    assert capsys.readouterr().err == ""


def test_run_automated_queues_list_unsubscribe_header_when_body_extract_fails() -> None:
    """Body allowlist may miss vendor links; List-Unsubscribe still carries HTTPS GET target."""
    m = _msg("z1", list_unsubscribe="<https://from-header.example/unsub>")
    facade = GmailFacade(_B())
    browser_row = {
        "email_index": 3,
        "subject": "S",
        "sender": "A <a@list-manage.com>",
        "method": "browser",
        "status": "confirmed",
        "detail": "ok",
    }
    with (
        patch(
            "unsubscribe.execution.try_one_click_unsubscribe",
            side_effect=UnsubscribeNotOneClickError("not advertised"),
        ),
        patch("unsubscribe.execution.batch_browser_unsubscribe") as mock_batch,
        patch(
            "unsubscribe.execution.extract_unsubscribe_link",
            side_effect=NoUnsubscribeLinkError("no body"),
        ),
    ):
        mock_batch.return_value = [browser_row]
        rows = run_automated_unsubscribe(
            facade,
            [(3, m)],
            debugger_address="127.0.0.1:9222",
            verbose=False,
        )
    mock_batch.assert_called_once()
    jobs = mock_batch.call_args[0][0]
    assert len(jobs) == 1
    assert jobs[0][3] == "https://from-header.example/unsub"
    assert rows[0]["status"] == "confirmed"


def test_print_unsubscribe_report_outputs_truthful_footer(capsys) -> None:
    print_unsubscribe_report(
        [
            {
                "email_index": 2,
                "subject": "Weekly Deals",
                "sender": "deals@shop.example",
                "method": "one-click",
                "status": "server-acknowledged",
                "detail": "One-Click unsubscribe accepted (HTTP 200).",
            },
            {
                "email_index": None,
                "subject": "Daily Brief",
                "sender": "news@daily.com",
                "method": "browser",
                "status": "confirmed",
                "detail": "browser → unsubscribe confirmation seen on page ✓",
            },
        ]
    )
    text = capsys.readouterr().out
    assert "── Results ──" in text
    assert "may require further steps" in text
    assert "server accepted (200)" in text
    assert "attempted:" in text
    assert "confirmed" in text
    assert "server-acknowledged" in text
    assert "Unsubscribed from" not in text
