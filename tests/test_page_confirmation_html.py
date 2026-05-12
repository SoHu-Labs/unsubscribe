"""Saved-HTML confirmation scan (markers shared with live browser check)."""

from __future__ import annotations

from unsubscribe.page_confirmation_markers import (
    html_suggests_unsubscribe_confirmation,
    rough_text_from_html_for_confirmation,
)


def test_rough_text_from_html_strips_tags() -> None:
    html = "<html><body><p>You've been unsubscribed</p></body></html>"
    t = rough_text_from_html_for_confirmation(html)
    assert "unsubscribed" in t.lower()
    assert "<p>" not in t


def test_html_suggests_unsubscribe_confirmation_positive() -> None:
    html = "<div>You will no longer receive our newsletter.</div>"
    assert html_suggests_unsubscribe_confirmation(html) is True


def test_html_suggests_unsubscribe_confirmation_negative() -> None:
    html = "<div>Click here to manage preferences.</div>"
    assert html_suggests_unsubscribe_confirmation(html) is False
