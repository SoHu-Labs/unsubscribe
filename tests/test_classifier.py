"""Regression tests for newsletter classification (Iteration 2)."""

from __future__ import annotations

import json
from pathlib import Path

from unsubscribe.classifier import is_unsubscribable_newsletter

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "headers"


def _load_headers(name: str) -> dict[str, str]:
    path = _FIXTURES / name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return {str(k): str(v) for k, v in data.items()}


def test_newsletter_with_list_unsubscribe_header_is_candidate() -> None:
    headers = _load_headers("newsletter_with_header.json")
    assert is_unsubscribable_newsletter(headers) is True


def test_newsletter_body_link_only_with_bulk_precedence_is_candidate() -> None:
    headers = _load_headers("newsletter_body_link_only.json")
    assert is_unsubscribable_newsletter(headers, has_body_unsubscribe_link=True) is True


def test_personal_email_is_not_candidate() -> None:
    headers = _load_headers("personal_no.json")
    assert is_unsubscribable_newsletter(headers) is False
    assert is_unsubscribable_newsletter(headers, has_body_unsubscribe_link=False) is False


def test_transactional_with_unsubscribe_header_is_not_candidate() -> None:
    headers = _load_headers("transactional_with_header.json")
    assert is_unsubscribable_newsletter(headers) is False


def test_bulk_newsletter_without_unsubscribe_path_is_not_candidate() -> None:
    headers = _load_headers("newsletter_no_unsub_path.json")
    assert is_unsubscribable_newsletter(headers) is False
    assert is_unsubscribable_newsletter(headers, has_body_unsubscribe_link=False) is False


def test_newsletter_vendor_https_list_unsubscribe_without_mailchimp_is_candidate() -> None:
    """Airlines, travel, etc. use their own unsubscribe hosts (not ESP allowlist)."""
    headers = _load_headers("newsletter_generic_vendor_unsub.json")
    assert is_unsubscribable_newsletter(headers) is True


def test_newsletter_google_cloud_style_list_unsubscribe_is_candidate() -> None:
    headers = _load_headers("newsletter_google_cloud_style.json")
    assert is_unsubscribable_newsletter(headers) is True


def test_newsletter_list_unsubscribe_post_only_is_candidate() -> None:
    """Some senders expose RFC 8058 Post without repeating List-Unsubscribe in headers we see."""
    headers = _load_headers("newsletter_oneclick_post_header_only.json")
    assert is_unsubscribable_newsletter(headers) is True


def test_body_link_flag_without_bulk_signal_is_not_candidate() -> None:
    """Caller may pass has_body_unsubscribe_link=True, but (a) bulk must still hold."""
    headers = _load_headers("personal_no.json")
    assert is_unsubscribable_newsletter(headers, has_body_unsubscribe_link=True) is False
