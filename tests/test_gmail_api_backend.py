"""Gmail API backend: ``build`` and OAuth file I/O mocked."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from unsubscribe.gmail_api_backend import (
    GmailApiBackend,
    html_from_gmail_message_payload,
)
from unsubscribe.gmail_facade import GmailHeaderSummary


_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gmail"


def test_from_env_requires_goog_oauth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_OAUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GOOGLE_OAUTH_TOKEN"):
        GmailApiBackend.from_env()


def test_from_token_path_rejects_missing_file(tmp_path: Path) -> None:
    p = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="not a file"):
        GmailApiBackend.from_token_path(p)


@patch("unsubscribe.gmail_api_backend.Credentials.from_authorized_user_file")
def test_from_token_path_wraps_refresh_failure(
    mock_from_file: MagicMock, tmp_path: Path
) -> None:
    p = tmp_path / "tok.json"
    p.write_text("{}", encoding="utf-8")
    creds = MagicMock()
    creds.valid = False
    creds.expired = True
    creds.refresh_token = "rt"
    mock_from_file.return_value = creds

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("offline")

    creds.refresh = MagicMock(side_effect=boom)
    with pytest.raises(ValueError, match="Could not refresh"):
        GmailApiBackend.from_token_path(p)


def test_html_from_gmail_payload_multipart_alternative() -> None:
    html = "<p>Hello <b>you</b></p>"
    b64 = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": "cGk="}},
            {"mimeType": "text/html", "body": {"data": b64}},
        ],
    }
    assert html_from_gmail_message_payload(payload) == html


@patch("unsubscribe.gmail_api_backend.build")
def test_list_messages_calls_metadata_then_minimal_per_message(mock_build: MagicMock) -> None:
    meta = json.loads((_FIXTURES / "metadata_message.json").read_text(encoding="utf-8"))
    minimal = json.loads((_FIXTURES / "minimal_message.json").read_text(encoding="utf-8"))

    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg123", "threadId": "thr456"}],
    }
    get_mock = mock_service.users.return_value.messages.return_value.get
    get_exec = get_mock.return_value.execute
    get_exec.side_effect = [meta, minimal]

    backend = GmailApiBackend(credentials=MagicMock())
    out = backend.list_messages("newer_than:3d", max_results=5)

    assert out == [
        GmailHeaderSummary(
            id="msg123",
            thread_id="thr456",
            from_="News <newsletter@example.com>",
            subject="Weekly digest",
            date="Mon, 15 Apr 2024 10:00:00 +0000",
            snippet="This week: summer sale and free shipping…",
            list_unsubscribe="<https://example.com/unsub?id=1>",
            list_unsubscribe_post="List-Unsubscribe=One-Click",
        )
    ]

    list_call = mock_service.users.return_value.messages.return_value.list
    list_call.assert_called_once_with(userId="me", q="newer_than:3d", maxResults=5)
    assert get_mock.call_count == 2
    first = get_mock.call_args_list[0]
    second = get_mock.call_args_list[1]
    assert first.kwargs == {
        "userId": "me",
        "id": "msg123",
        "format": "metadata",
        "metadataHeaders": [
            "List-Unsubscribe",
            "List-Unsubscribe-Post",
            "Subject",
            "From",
            "Date",
        ],
    }
    assert second.kwargs == {"userId": "me", "id": "msg123", "format": "minimal"}


@patch("unsubscribe.gmail_api_backend.build")
def test_list_messages_empty_inbox(mock_build: MagicMock) -> None:
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {}

    backend = GmailApiBackend(credentials=MagicMock())
    assert backend.list_messages("none") == []


@patch("unsubscribe.gmail_api_backend.build")
def test_get_message_html_uses_full_format(mock_build: MagicMock) -> None:
    html = "<html><body><a href=\"https://x.test\">x</a></body></html>"
    b64 = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    get_chain = mock_service.users.return_value.messages.return_value.get.return_value
    get_chain.execute.return_value = {
        "id": "m2",
        "payload": {"mimeType": "text/html", "body": {"data": b64}},
    }
    backend = GmailApiBackend(credentials=MagicMock())
    out = backend.get_message_html("m2")
    assert out == html
    mock_service.users.return_value.messages.return_value.get.assert_called_once_with(
        userId="me",
        id="m2",
        format="full",
    )


@patch("unsubscribe.gmail_api_backend.build")
def test_get_message_body_text_strips_html_and_truncates(mock_build: MagicMock) -> None:
    long_inner = "word " * 200  # >500 chars after strip
    html = f"<div><p>Hi</p><script>x</script><p>{long_inner}</p></div>"
    b64 = base64.urlsafe_b64encode(html.encode()).decode().rstrip("=")
    mock_service = MagicMock()
    mock_build.return_value = mock_service
    get_chain = mock_service.users.return_value.messages.return_value.get.return_value
    get_chain.execute.return_value = {
        "id": "m3",
        "payload": {"mimeType": "text/html", "body": {"data": b64}},
    }
    backend = GmailApiBackend(credentials=MagicMock())
    out = backend.get_message_body_text("m3")
    full = ("Hi " + long_inner.strip())
    assert out == full[:500]
    assert len(out) == 500
