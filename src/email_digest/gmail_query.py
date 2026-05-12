"""Build Gmail ``q`` strings for digest collection."""

from __future__ import annotations

from datetime import date


def sender_pattern_to_from_clause(pattern: str) -> str:
    """Map a topic YAML ``senders`` entry to a Gmail ``from:`` atom."""
    p = pattern.strip()
    if p.startswith("*@"):
        return f"from:{p[2:].strip()}"
    if p.endswith("@*"):
        return f"from:{p[:-2].strip()}"
    if "@" in p:
        return f"from:{p}"
    return f"from:{p}"


def build_digest_gmail_query(
    *,
    window_days: int,
    senders: list[str],
    folders: list[str] | None,
    since: date | None = None,
) -> str:
    if not senders:
        raise ValueError("senders must be non-empty")
    parts: list[str] = []
    if since is not None:
        parts.append(f"after:{since.year}/{since.month}/{since.day}")
    else:
        parts.append(f"newer_than:{window_days}d")
    parts.append("-in:chats")

    folders = list(folders or ("INBOX",))
    for raw in folders:
        f = raw.strip()
        if not f:
            continue
        if f.upper() == "INBOX":
            parts.append("in:inbox")
        else:
            esc = f.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'label:"{esc}"')

    clauses = [sender_pattern_to_from_clause(s) for s in senders]
    if len(clauses) == 1:
        parts.append(clauses[0])
    else:
        parts.append("(" + " OR ".join(clauses) + ")")
    return " ".join(parts)
