"""Repo-root resolution (shared by CLI, cache, topics)."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "pyproject.toml").is_file():
            return p
    raise RuntimeError("Could not locate repo root (pyproject.toml)")


def default_cache_db_path() -> Path:
    override = os.environ.get("DIGEST_CACHE_DB", "").strip()
    if override:
        p = Path(override).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    d = repo_root() / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / "digest.sqlite"
