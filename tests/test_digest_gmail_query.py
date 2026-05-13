"""Gmail search query construction for digest collection."""

from __future__ import annotations

from datetime import date

import pytest

from email_digest.gmail_query import build_digest_gmail_query


def test_build_query_newer_than_and_inbox() -> None:
    q = build_digest_gmail_query(
        window_days=7,
        senders=["news@example.com"],
        folders=["INBOX"],
    )
    assert "newer_than:7d" in q
    assert "-in:chats" in q
    assert "in:inbox" in q.casefold()
    assert "from:news@example.com" in q


def test_build_query_multiple_senders_uses_or() -> None:
    q = build_digest_gmail_query(
        window_days=3,
        senders=["a@x.com", "b@y.com"],
        folders=["INBOX"],
    )
    assert "OR" in q
    assert "from:a@x.com" in q
    assert "from:b@y.com" in q


def test_build_query_wildcard_domain() -> None:
    q = build_digest_gmail_query(
        window_days=7,
        senders=["*@thealgorithm.com"],
        folders=["INBOX"],
    )
    assert "from:thealgorithm.com" in q


def test_build_query_since_replaces_newer_than_window() -> None:
    q = build_digest_gmail_query(
        window_days=7,
        senders=["a@b.com"],
        folders=["INBOX"],
        since=date(2026, 5, 1),
    )
    assert "after:2026/5/1" in q
    assert "newer_than:" not in q


def test_build_query_non_inbox_folder_adds_label() -> None:
    q = build_digest_gmail_query(
        window_days=7,
        senders=["a@b.com"],
        folders=["INBOX", "AI Newsletters"],
    )
    assert "in:inbox" in q.casefold()
    assert 'label:"AI Newsletters"' in q


def test_build_query_empty_senders_and_keywords_raises() -> None:
    with pytest.raises(ValueError, match="senders or keywords"):
        build_digest_gmail_query(window_days=7, senders=[], folders=["INBOX"])


def test_build_query_keywords_broadens_search() -> None:
    q = build_digest_gmail_query(
        window_days=7,
        senders=["a@x.com"],
        keywords=["machine learning", "benchmark"],
        folders=["INBOX"],
    )
    assert "from:a@x.com" in q
    assert "(machine learning)" in q
    assert "(benchmark)" in q
    assert "OR" in q


def test_build_query_keywords_without_senders() -> None:
    q = build_digest_gmail_query(
        window_days=7,
        senders=[],
        keywords=["ai safety", "alignment"],
        folders=["INBOX"],
    )
    assert "(ai safety)" in q
    assert "(alignment)" in q
    assert "from:" not in q
