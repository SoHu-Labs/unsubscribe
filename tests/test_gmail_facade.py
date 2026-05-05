"""GmailFacade wraps a GmailBackend with consistent transport errors."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from unsubscribe.gmail_facade import (
    GmailFacade,
    GmailHeaderSummary,
    GmailTransportError,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gmail"


def _sample_summary() -> GmailHeaderSummary:
    return GmailHeaderSummary(
        id="m1",
        thread_id="t1",
        from_="a@b.com",
        subject="Subj",
        date="Mon, 1 Jan 2024 00:00:00 +0000",
        snippet="snip",
        list_unsubscribe="<mailto:x@y.com>",
        list_unsubscribe_post=None,
    )


def test_facade_list_messages_delegates_to_backend() -> None:
    backend = MagicMock()
    s = _sample_summary()
    backend.list_messages.return_value = [s]
    facade = GmailFacade(backend)
    out = facade.list_messages("newer_than:1d", max_results=3)
    backend.list_messages.assert_called_once_with("newer_than:1d", max_results=3)
    assert out == [s]


def test_facade_get_message_html_delegates_to_backend() -> None:
    backend = MagicMock()
    backend.get_message_html.return_value = "<html></html>"
    facade = GmailFacade(backend)
    assert facade.get_message_html("mid") == "<html></html>"
    backend.get_message_html.assert_called_once_with("mid")


def test_facade_get_message_body_text_delegates_to_backend() -> None:
    backend = MagicMock()
    backend.get_message_body_text.return_value = "plain"
    facade = GmailFacade(backend)
    assert facade.get_message_body_text("mid") == "plain"
    backend.get_message_body_text.assert_called_once_with("mid")


def test_facade_wraps_unexpected_backend_errors_as_transport_error() -> None:
    backend = MagicMock()
    backend.list_messages.side_effect = OSError("nope")
    facade = GmailFacade(backend)
    with pytest.raises(GmailTransportError) as excinfo:
        facade.list_messages("q")
    assert "nope" in str(excinfo.value)


def test_facade_does_not_double_wrap_gmail_transport_error() -> None:
    backend = MagicMock()
    backend.get_message_html.side_effect = GmailTransportError("already")
    facade = GmailFacade(backend)
    with pytest.raises(GmailTransportError, match="already"):
        facade.get_message_html("x")


def test_facade_metadata_fixture_headers_match_expected_shape() -> None:
    """Lock committed fixture shape used by backend tests."""
    raw = json.loads((_FIXTURES / "metadata_message.json").read_text(encoding="utf-8"))
    headers = {h["name"]: h["value"] for h in raw["payload"]["headers"]}
    assert headers["Subject"] == "Weekly digest"
    assert "List-Unsubscribe" in headers
