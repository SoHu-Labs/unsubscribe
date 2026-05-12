"""Optional digest HTML delivery via Gmail API (same OAuth as unsubscribe / digest read)."""

from __future__ import annotations

from email_digest.config import TopicConfig
from unsubscribe.gmail_facade import GmailFacade


def resolve_digest_recipient(
    also_email_to: str | None, *, profile_email: str
) -> str | None:
    """Return ``To`` address, or ``None`` when email output is disabled."""
    if also_email_to is None or not (raw := also_email_to.strip()):
        return None
    if raw.lower() == "self":
        return profile_email.strip() or None
    if "@" in raw:
        return raw
    raise ValueError(
        f"Unknown output.also_email_to value {also_email_to!r}; "
        'use "self" or a full email address.'
    )


def digest_email_subject(cfg: TopicConfig, *, date_iso: str) -> str:
    try:
        return cfg.display_name.format(date=date_iso)
    except (KeyError, IndexError, ValueError):
        return cfg.display_name.replace("{date}", date_iso)


def maybe_email_digest(
    cfg: TopicConfig,
    html: str,
    *,
    date_iso: str,
    facade: GmailFacade,
) -> str | None:
    """If configured, send the digest HTML via Gmail API; return recipient or ``None``."""
    if cfg.also_email_to is None or not str(cfg.also_email_to).strip():
        return None
    profile_email = facade.get_profile_email()
    to_addr = resolve_digest_recipient(cfg.also_email_to, profile_email=profile_email)
    if to_addr is None:
        return None
    subject = digest_email_subject(cfg, date_iso=date_iso)
    facade.send_html_email(to=to_addr, subject=subject, html=html)
    return to_addr
