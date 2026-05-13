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
    keywords: list[str] | None = None,
    folders: list[str] | None = None,
    since: date | None = None,
) -> str:
    if not senders and not keywords:
        raise ValueError("at least one of senders or keywords must be non-empty")
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

    match_clauses: list[str] = []
    if senders:
        sc = [sender_pattern_to_from_clause(s) for s in senders]
        match_clauses.append("(" + " OR ".join(sc) + ")" if len(sc) > 1 else sc[0])
    if keywords:
        kw = [f"({k})" for k in keywords]
        match_clauses.append("(" + " OR ".join(kw) + ")" if len(kw) > 1 else kw[0])

    if len(match_clauses) == 1:
        parts.append(match_clauses[0])
    else:
        parts.append("(" + " OR ".join(match_clauses) + ")")
    return " ".join(parts)
