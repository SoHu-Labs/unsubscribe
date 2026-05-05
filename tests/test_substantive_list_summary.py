"""Tests for list-view summary (skip Gmail preamble; prefer article lede)."""

from __future__ import annotations

from unsubscribe.cli import substantive_list_summary


def test_substantive_summary_skips_view_in_browser_and_signup_preamble() -> None:
    body = (
        "View this email in your browser 👋 Did this email get forwarded to you? "
        "Sign up here to get Today, Explained daily. "
        "Today, Explained the newsletter May 5, 2026 Everyone has a Spirit story. "
        "None of them are good. In 2016, I flew Spirit from Baltimore to Atlanta for"
    )
    out = substantive_list_summary("", body)
    assert out.startswith("Everyone has a Spirit story")


def test_substantive_summary_uses_body_before_snippet_when_snippet_is_preamble() -> None:
    snip = "View this email in your browser. Great article about whales here."
    body = "Here is the real story. Blue whales migrate farther than we thought."
    out = substantive_list_summary(snip, body)
    assert "view this email" not in out.casefold()
    assert "real story" in out.casefold()


def test_substantive_summary_falls_back_to_clean_snippet() -> None:
    out = substantive_list_summary("A concise factual snippet about the budget.", "")
    assert "budget" in out.lower()
