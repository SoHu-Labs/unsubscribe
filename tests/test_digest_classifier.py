"""Digest-side use of newsletter heuristics (slice B) — must stay aligned with unsubscribe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from unsubscribe.classifier import (
    is_digest_source_candidate,
    is_unsubscribable_newsletter,
)

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "headers"


def _load_headers(name: str) -> dict[str, str]:
    path = _FIXTURES / name
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return {str(k): str(v) for k, v in data.items()}


@pytest.mark.parametrize(
    ("fixture", "body_link"),
    [
        ("newsletter_with_header.json", False),
        ("newsletter_body_link_only.json", True),
        ("personal_no.json", False),
        ("personal_no.json", True),
        ("transactional_with_header.json", False),
        ("newsletter_no_unsub_path.json", False),
        ("newsletter_generic_vendor_unsub.json", False),
        ("newsletter_google_cloud_style.json", False),
        ("newsletter_oneclick_post_header_only.json", False),
    ],
)
def test_digest_source_candidate_matches_unsubscribable_newsletter(
    fixture: str, body_link: bool
) -> None:
    headers = _load_headers(fixture)
    assert is_digest_source_candidate(
        headers, has_body_unsubscribe_link=body_link
    ) == is_unsubscribable_newsletter(headers, has_body_unsubscribe_link=body_link)
