"""Digest optional delivery via Gmail API (facade)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from email_digest.config import TopicConfig, load_topic_config
from email_digest.digest_mail import (
    digest_email_subject,
    maybe_email_digest,
    resolve_digest_recipient,
)
from unsubscribe.gmail_facade import GmailFacade


def test_resolve_digest_recipient_none() -> None:
    assert resolve_digest_recipient(None, profile_email="me@gmail.com") is None
    assert resolve_digest_recipient("", profile_email="me@gmail.com") is None


def test_resolve_digest_recipient_self() -> None:
    assert (
        resolve_digest_recipient("self", profile_email="me@gmail.com") == "me@gmail.com"
    )


def test_resolve_digest_recipient_address() -> None:
    assert (
        resolve_digest_recipient(
            "other@example.com", profile_email="me@gmail.com"
        )
        == "other@example.com"
    )


def test_resolve_digest_recipient_unknown() -> None:
    with pytest.raises(ValueError, match="also_email_to"):
        resolve_digest_recipient("not-an-email", profile_email="me@gmail.com")


def test_digest_email_subject_format() -> None:
    cfg = TopicConfig(
        name="x",
        display_name="Week of {date}",
        senders=(),
        folders=("INBOX",),
        window_days=7,
        extract_model="fast",
        synthesize_model="smart",
        persona_prompt="p",
        trending_min_cluster_size=2,
        trending_similarity_threshold=0.5,
        trending_algorithm="hdbscan",
        output_template="digest_html",
        also_email_to=None,
    )
    assert digest_email_subject(cfg, date_iso="2026-05-12") == "Week of 2026-05-12"


def test_maybe_email_digest_skips_when_disabled() -> None:
    cfg = TopicConfig(
        name="x",
        display_name="D",
        senders=(),
        folders=("INBOX",),
        window_days=7,
        extract_model="fast",
        synthesize_model="smart",
        persona_prompt="p",
        trending_min_cluster_size=2,
        trending_similarity_threshold=0.5,
        trending_algorithm="hdbscan",
        output_template="digest_html",
        also_email_to=None,
    )
    backend = MagicMock()
    facade = GmailFacade(backend)
    assert (
        maybe_email_digest(cfg, "<p>x</p>", date_iso="2026-01-01", facade=facade)
        is None
    )
    backend.get_profile_email.assert_not_called()


def test_maybe_email_digest_calls_facade() -> None:
    cfg = TopicConfig(
        name="x",
        display_name="R {date}",
        senders=(),
        folders=("INBOX",),
        window_days=7,
        extract_model="fast",
        synthesize_model="smart",
        persona_prompt="p",
        trending_min_cluster_size=2,
        trending_similarity_threshold=0.5,
        trending_algorithm="hdbscan",
        output_template="digest_html",
        also_email_to="self",
    )
    backend = MagicMock()
    backend.get_profile_email.return_value = "me@gmail.com"
    facade = GmailFacade(backend)
    got = maybe_email_digest(cfg, "<html></html>", date_iso="2026-02-02", facade=facade)
    assert got == "me@gmail.com"
    backend.get_profile_email.assert_called_once_with()
    backend.send_html_email.assert_called_once_with(
        to="me@gmail.com",
        subject="R 2026-02-02",
        html="<html></html>",
    )


def test_load_topic_config_includes_also_email_to(tmp_path: Path) -> None:
    p = tmp_path / "t.yaml"
    p.write_text(
        """
name: t
display_name: "T {date}"
senders: ["a@b.com"]
window_days: 7
extract_model: fast
synthesize_model: smart
persona_prompt: "x"
output:
  also_email_to: friend@example.com
""",
        encoding="utf-8",
    )
    cfg = load_topic_config(p)
    assert cfg.also_email_to == "friend@example.com"
