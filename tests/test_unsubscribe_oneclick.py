"""Tests for RFC 2369 / RFC 8058 one-click unsubscribe parsing and POST (Iteration 5)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from unsubscribe.unsubscribe_oneclick import (
    NoUnsubscribeHeaderError,
    UnsubscribeNotOneClickError,
    UnsubscribePostRedirectError,
    parse_list_unsubscribe,
    try_one_click_unsubscribe,
)


def _mock_http_response(code: int) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    mock_resp.getcode.return_value = code
    return mock_resp

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "headers"


def _load_headers(name: str) -> dict[str, str]:
    path = _FIXTURES / name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return {str(k): str(v) for k, v in data.items()}


def test_parse_list_unsubscribe_angle_brackets_and_whitespace() -> None:
    raw = " <https://a.example/unsub> , <mailto:x@y.com> "
    assert parse_list_unsubscribe(raw) == [
        "https://a.example/unsub",
        "mailto:x@y.com",
    ]


def test_parse_list_unsubscribe_bare_urls_without_brackets() -> None:
    raw = "https://b.example/u,mailto:z@w.org"
    assert parse_list_unsubscribe(raw) == [
        "https://b.example/u",
        "mailto:z@w.org",
    ]


def test_parse_list_unsubscribe_case_insensitive_mailto_scheme() -> None:
    raw = "<MAILTO:List@Vendor.COM>"
    assert parse_list_unsubscribe(raw) == ["mailto:List@Vendor.COM"]


def test_try_one_click_missing_list_unsubscribe_raises() -> None:
    with pytest.raises(NoUnsubscribeHeaderError):
        try_one_click_unsubscribe({})


def test_try_one_click_empty_list_unsubscribe_raises() -> None:
    with pytest.raises(NoUnsubscribeHeaderError):
        try_one_click_unsubscribe({"List-Unsubscribe": "  "})


def test_try_one_click_no_post_header_raises() -> None:
    headers = _load_headers("oneclick_no_post_header.json")
    with pytest.raises(UnsubscribeNotOneClickError):
        try_one_click_unsubscribe(headers)


def test_try_one_click_post_header_wrong_value_raises() -> None:
    headers = {
        "List-Unsubscribe": "<https://example.com/unsub>",
        "List-Unsubscribe-Post": "something-else",
    }
    with pytest.raises(UnsubscribeNotOneClickError):
        try_one_click_unsubscribe(headers)


def test_try_one_click_header_key_case_insensitive() -> None:
    headers = {
        "list-unsubscribe": "<https://example.org/x>",
        "list-unsubscribe-post": "List-Unsubscribe=One-Click",
    }
    mock_resp = _mock_http_response(200)
    with patch(
        "unsubscribe.unsubscribe_oneclick._urlopen_no_redirect",
        return_value=mock_resp,
    ) as mock_open:
        out = try_one_click_unsubscribe(headers)
    assert "200" in out
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    assert req.full_url == "https://example.org/x"
    assert req.data == b"List-Unsubscribe=One-Click"
    assert req.get_header("Content-type") == "application/x-www-form-urlencoded"


def test_try_one_click_success_with_fixture_and_mocked_post() -> None:
    headers = _load_headers("oneclick_yes.json")
    mock_resp = _mock_http_response(204)
    with patch(
        "unsubscribe.unsubscribe_oneclick._urlopen_no_redirect",
        return_value=mock_resp,
    ) as mock_open:
        msg = try_one_click_unsubscribe(headers)
    assert "204" in msg
    req = mock_open.call_args[0][0]
    assert req.full_url == "https://lists.example.test/unsubscribe?token=abc"
    assert req.data == b"List-Unsubscribe=One-Click"


def test_try_one_click_https_only_no_http_for_one_click() -> None:
    headers = {
        "List-Unsubscribe": "<http://insecure.example/u>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    with pytest.raises(UnsubscribeNotOneClickError):
        try_one_click_unsubscribe(headers)


def test_try_one_click_mailto_only_returns_manual_message() -> None:
    headers = _load_headers("oneclick_mailto_only.json")
    msg = try_one_click_unsubscribe(headers)
    assert "manual action" in msg.lower()
    assert "newsletter@acme.test" in msg


def test_try_one_click_post_redirect_raises() -> None:
    headers = _load_headers("oneclick_yes.json")
    with patch(
        "unsubscribe.unsubscribe_oneclick._urlopen_no_redirect",
        side_effect=UnsubscribePostRedirectError(302, "Found"),
    ):
        with pytest.raises(UnsubscribePostRedirectError) as excinfo:
            try_one_click_unsubscribe(headers)
    assert excinfo.value.status_code == 302


def test_try_one_click_malformed_list_unsubscribe_raises() -> None:
    headers = _load_headers("oneclick_malformed.json")
    with pytest.raises(NoUnsubscribeHeaderError):
        try_one_click_unsubscribe(headers)
