"""Newsletter unsubscribe assistant package."""

from __future__ import annotations

__all__ = ["sanitize_filename"]

# Characters unsafe in filenames (Windows + path separators).
_FORBIDDEN_FILENAME_CHARS = frozenset('<>:"|?*/\\')


def sanitize_filename(name: str) -> str:
    """Return a filesystem-safer filename; empty or whitespace-only → ``unnamed``."""
    out_chars: list[str] = []
    for ch in name:
        if ch in _FORBIDDEN_FILENAME_CHARS:
            out_chars.append("_")
        elif ord(ch) < 32:
            out_chars.append("_")
        else:
            out_chars.append(ch)
    out = "".join(out_chars).strip(" .")
    return out if out else "unnamed"
