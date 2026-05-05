"""Smoke tests: package import and small pure helpers."""

from unsubscribe import sanitize_filename


def test_sanitize_filename_replaces_path_separators() -> None:
    assert sanitize_filename("weekly/deals") == "weekly_deals"


def test_sanitize_filename_strips_windows_forbidden_chars() -> None:
    assert sanitize_filename('Report<>:"|?*.pdf') == "Report_______.pdf"


def test_sanitize_filename_collapses_non_printables_to_placeholder() -> None:
    assert sanitize_filename("a\x00b\nc") == "a_b_c"


def test_sanitize_filename_empty_becomes_unnamed() -> None:
    assert sanitize_filename("   ") == "unnamed"
    assert sanitize_filename("") == "unnamed"
