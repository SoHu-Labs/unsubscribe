"""Heuristics for whether a message is an unsubscribable marketing/newsletter email."""

from __future__ import annotations

# Host/path fragments typical of legitimate list providers (restrictive allowlist).
_LIST_HOST_MARKERS: tuple[str, ...] = (
    "list-manage.com",
    "mailchimp",
    "substack.com",
    "convertkit",
    "sendgrid",
    "constantcontact",
    "hubspot",
    "listrak",
    "cmail",
    "createsend.com",
)


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {name.strip().lower(): value for name, value in headers.items()}


def _has_unsubscribe_path(norm: dict[str, str], *, has_body_unsubscribe_link: bool) -> bool:
    lu = (norm.get("list-unsubscribe") or "").strip()
    if lu:
        return True
    return has_body_unsubscribe_link


def _transactional(norm: dict[str, str]) -> bool:
    """Exclude obvious transactional / account traffic even with List-Unsubscribe."""
    from_ = (norm.get("from") or "").lower()
    subject = (norm.get("subject") or "").lower()
    if "github.com" in from_ or "noreply@github" in from_:
        return True
    if subject.startswith("[github") or "[github/" in subject:
        return True
    return False


def _bulk_marketing(norm: dict[str, str]) -> bool:
    precedence = (norm.get("precedence") or "").strip().lower()
    if precedence == "bulk":
        return True
    from_ = (norm.get("from") or "").lower()
    if any(h in from_ for h in ("newsletter@", "digest@", "marketing@", "mailer@")):
        return True
    lu = (norm.get("list-unsubscribe") or "").lower()
    if lu and any(marker in lu for marker in _LIST_HOST_MARKERS):
        return True
    return False


def is_unsubscribable_newsletter(
    headers: dict[str, str],
    *,
    has_body_unsubscribe_link: bool = False,
) -> bool:
    """
    Return True only when the message looks like bulk/marketing and the caller can
    unsubscribe (header and/or confirmed body link).
    """
    norm = _normalize_headers(headers)
    if not _has_unsubscribe_path(norm, has_body_unsubscribe_link=has_body_unsubscribe_link):
        return False
    if _transactional(norm):
        return False
    if not _bulk_marketing(norm):
        return False
    return True
