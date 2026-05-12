"""Tests for HTML body unsubscribe link extraction (Iteration 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from unsubscribe.unsubscribe_link import (
    NoUnsubscribeLinkError,
    UnsafeLinkError,
    extract_unsubscribe_link,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "mail"


def _load_html(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_extract_happy_path_fixture() -> None:
    html = _load_html("newsletter_with_unsubscribe_link.html")
    url = extract_unsubscribe_link(html)
    assert url.startswith("https://")
    assert "list-manage.com" in url
    assert "unsubscribe" in url.lower()


def test_no_unsubscribe_link_raises() -> None:
    html = _load_html("newsletter_no_unsubscribe_link.html")
    with pytest.raises(NoUnsubscribeLinkError) as exc:
        extract_unsubscribe_link(html)
    assert "list-unsubscribe" in str(exc.value).lower() or "header" in str(exc.value).lower()


def test_ambiguous_links_raise() -> None:
    html = _load_html("newsletter_ambiguous.html")
    with pytest.raises(NoUnsubscribeLinkError):
        extract_unsubscribe_link(html)


def test_javascript_href_is_unsafe() -> None:
    html = _load_html("newsletter_javascript_link.html")
    with pytest.raises(UnsafeLinkError) as exc:
        extract_unsubscribe_link(html)
    assert "javascript" in str(exc.value).lower()


def test_ip_host_is_unsafe() -> None:
    html = _load_html("newsletter_ip_link.html")
    with pytest.raises(UnsafeLinkError) as exc:
        extract_unsubscribe_link(html)
    assert "192.168" in str(exc.value) or "ip" in str(exc.value).lower()


def test_title_attribute_counts_as_signal() -> None:
    html = """<html><body><a href="https://vendor.us1.list-manage.com/u/x"
        title="Unsubscribe from list">Quiet link</a></body></html>"""
    url = extract_unsubscribe_link(html)
    assert "list-manage.com" in url


def test_unknown_host_with_matching_text_skipped() -> None:
    html = """<html><body>
        <a href="https://evil-phish.example/unsub">Unsubscribe</a>
    </body></html>"""
    with pytest.raises(NoUnsubscribeLinkError):
        extract_unsubscribe_link(html)


def test_extract_wizzair_allows_marketing_site() -> None:
    html = """<html><body>
        <a href="https://www.wizzair.com/en-gb/newsletter-unsubscribe">Unsubscribe</a>
    </body></html>"""
    url = extract_unsubscribe_link(html)
    assert "wizzair.com" in url


def test_data_uri_is_unsafe() -> None:
    html = """<html><body>
        <a href="data:text/html,&lt;base href=&quot;https://x&quot;/&gt;">Unsubscribe</a>
    </body></html>"""
    with pytest.raises(UnsafeLinkError):
        extract_unsubscribe_link(html)
