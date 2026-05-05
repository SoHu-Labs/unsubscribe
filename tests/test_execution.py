"""Tests for post-check automated unsubscribe orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from unsubscribe.execution import run_automated_unsubscribe
from unsubscribe.gmail_facade import GmailFacade, GmailHeaderSummary


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


def test_run_automated_one_click_counts_plus_browser() -> None:
    m1 = _msg("1", list_unsubscribe="<https://u.test/x>", list_unsubscribe_post="List-Unsubscribe=One-Click")
    m2 = _msg("2", list_unsubscribe=None)
    facade = GmailFacade(_B())

    with (
        patch("unsubscribe.execution.try_one_click_unsubscribe") as mock_1c,
        patch("unsubscribe.execution.batch_browser_unsubscribe") as mock_batch,
    ):
        mock_1c.side_effect = [
            "One-Click unsubscribe accepted (HTTP 204).",
            "manual",
        ]
        mock_batch.return_value = {"https://allow.example/u": True}

        def _extract(html: str) -> str:
            return "https://allow.example/u"

        with patch("unsubscribe.execution.extract_unsubscribe_link", side_effect=_extract):
            report = run_automated_unsubscribe(
                facade,
                [m1, m2],
                debugger_address="127.0.0.1:9222",
                verbose=False,
            )

    assert len(report) == 2
    assert report.verified_success_count == 2
    assert {o.status for o in report.outcomes} == {"one_click_ok", "browser_ok"}
    mock_batch.assert_called_once()


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
        report = run_automated_unsubscribe(
            facade,
            [m],
            debugger_address=None,
            verbose=False,
        )

    mock_batch.assert_not_called()
    assert len(report) == 1
    assert report.verified_success_count == 0
    assert report.outcomes[0].status == "browser_skipped"
    assert "UNSUBSCRIBE_BROWSER_DEBUGGER_ADDRESS" in report.outcomes[0].detail
    # no stderr warning path; detail lives on the outcome for printing by the CLI
    assert capsys.readouterr().err == ""
