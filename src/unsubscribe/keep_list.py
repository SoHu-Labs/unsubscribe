"""Local keep-list (~/.unsubscribe_keep.json) for senders the user chose to keep."""

from __future__ import annotations

import json
from datetime import date
from email.utils import parseaddr
from pathlib import Path
from typing import Any


def sender_key(from_header: str) -> str | None:
    """Return lowercased address from ``From`` header, or ``None`` if missing/invalid."""
    _, addr = parseaddr(from_header)
    a = addr.strip()
    if not a:
        return None
    return a.lower()


def is_kept(keep_list: dict[str, dict], from_header: str) -> bool:
    key = sender_key(from_header)
    if key is None:
        return False
    return key in keep_list


def load_keep_list(path: Path) -> dict[str, dict]:
    """Load JSON object; create ``path`` with ``{{}}`` when missing."""
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return {}
    raw = path.read_text(encoding="utf-8").strip() or "{}"
    data = json.loads(raw)
    return dict(data)  # shallow copy for safe mutation


def save_keep_list(path: Path, data: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def add_to_keep_list(path: Path, from_header: str, subject: str) -> None:
    key = sender_key(from_header)
    if key is None:
        return
    data = load_keep_list(path)
    data[key] = {"subject": subject, "date_kept": date.today().isoformat()}
    save_keep_list(path, data)


def remove_from_keep_list(path: Path, from_header: str) -> None:
    key = sender_key(from_header)
    if key is None:
        return
    data = load_keep_list(path)
    data.pop(key, None)
    save_keep_list(path, data)


def merge_keep_list(path: Path, fragment: dict[str, Any]) -> None:
    """Merge *fragment* into the keep file (same schema as ``save_keep_list``).

    Keys are normalized to lowercase. Each value must be a JSON object; missing
    ``subject`` / ``date_kept`` are filled with ``""`` and today's ISO date.
    """
    if not isinstance(fragment, dict):
        raise TypeError("merge input must be a JSON object")
    data = load_keep_list(path)
    today = date.today().isoformat()
    for k, v in fragment.items():
        key = str(k).strip().lower()
        if not key:
            raise ValueError("empty sender key in merge fragment")
        if not isinstance(v, dict):
            raise ValueError(f"value for {key!r} must be a JSON object")
        data[key] = {
            "subject": str(v.get("subject", "")),
            "date_kept": str(v.get("date_kept", today)),
        }
    save_keep_list(path, data)
