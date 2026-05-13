"""Tests for ~/.unsubscribe_keep.json helpers (Iteration 4)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from unsubscribe.keep_list import (
    add_to_keep_list,
    is_kept,
    load_keep_list,
    merge_keep_list,
    remove_from_keep_list,
    save_keep_list,
    sender_key,
)


def test_sender_key_parses_angle_bracket_from() -> None:
    assert sender_key('"News" <news@example.com>') == "news@example.com"


def test_sender_key_bare_address() -> None:
    assert sender_key("solo@example.com") == "solo@example.com"


def test_sender_key_empty_angle_brackets_returns_none() -> None:
    assert sender_key("<>") is None


def test_sender_key_empty_string_returns_none() -> None:
    assert sender_key("") is None


def test_sender_key_whitespace_only_returns_none() -> None:
    assert sender_key("   ") is None
    assert sender_key(" ") is None


def test_is_kept_false_when_sender_key_none() -> None:
    assert is_kept({"a@b.com": {}}, "") is False


def test_is_kept_true_when_key_present() -> None:
    assert is_kept({"news@example.com": {"subject": "x", "date_kept": "2024-01-01"}}, "News <news@example.com>") is True


def test_load_keep_list_creates_empty_file(tmp_path: Path) -> None:
    p = tmp_path / ".unsubscribe_keep.json"
    assert not p.exists()
    data = load_keep_list(p)
    assert data == {}
    assert p.read_text(encoding="utf-8").strip() == "{}"


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    payload = {"a@b.com": {"subject": "S", "date_kept": "2024-06-01"}}
    save_keep_list(p, payload)
    assert load_keep_list(p) == payload


def test_add_to_keep_list_persists_and_merges(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    load_keep_list(p)
    add_to_keep_list(p, "One <a@x.com>", "Sub A")
    add_to_keep_list(p, "B <b@x.com>", "Sub B")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert set(data.keys()) == {"a@x.com", "b@x.com"}
    assert data["a@x.com"]["subject"] == "Sub A"


def test_add_to_keep_list_noop_when_sender_key_none(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    load_keep_list(p)
    with patch("unsubscribe.keep_list.sender_key", return_value=None):
        add_to_keep_list(p, "???", "Sub")
    assert json.loads(p.read_text(encoding="utf-8")) == {}


def test_remove_from_keep_list(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    save_keep_list(p, {"z@z.com": {"subject": "Z", "date_kept": "d"}})
    remove_from_keep_list(p, "Z <z@z.com>")
    assert load_keep_list(p) == {}


def test_dedup_by_sender_overwrites_subject(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    add_to_keep_list(p, "N <n@n.com>", "First")
    add_to_keep_list(p, "N <n@n.com>", "Second")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["n@n.com"]["subject"] == "Second"


def test_merge_keep_list_merges_and_lowercases_keys(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    save_keep_list(p, {"old@o.com": {"subject": "O", "date_kept": "2020-01-01"}})
    merge_keep_list(
        p,
        {
            "NEW@X.COM": {"subject": "Nx", "date_kept": "2026-02-01"},
            "old@o.com": {"subject": "Updated", "date_kept": "2026-03-01"},
        },
    )
    data = load_keep_list(p)
    assert set(data.keys()) == {"old@o.com", "new@x.com"}
    assert data["new@x.com"]["subject"] == "Nx"
    assert data["old@o.com"]["subject"] == "Updated"


def test_merge_keep_list_rejects_non_object_fragment(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    load_keep_list(p)
    with pytest.raises(TypeError):
        merge_keep_list(p, [])  # type: ignore[arg-type]


def test_merge_keep_list_rejects_bad_value_type(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    load_keep_list(p)
    with pytest.raises(ValueError, match="must be a JSON object"):
        merge_keep_list(p, {"a@a.com": "not-an-object"})  # type: ignore[arg-type]


def test_merge_keep_list_rejects_empty_key(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    load_keep_list(p)
    with pytest.raises(ValueError, match="empty sender key"):
        merge_keep_list(p, {"": {"subject": "x", "date_kept": "2026-01-01"}})


def test_merge_keep_list_fills_defaults_for_partial_entry(tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    load_keep_list(p)
    merge_keep_list(p, {"only@k.com": {}})
    data = load_keep_list(p)
    assert data["only@k.com"]["subject"] == ""
    assert data["only@k.com"]["date_kept"] == date.today().isoformat()
