"""Heuristics for whether a message is an unsubscribable marketing/newsletter email."""

from __future__ import annotations


def _normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {name.strip().lower(): value for name, value in headers.items()}


def _has_unsubscribe_path(norm: dict[str, str], *, has_body_unsubscribe_link: bool) -> bool:
    if (norm.get("list-unsubscribe") or "").strip():
        return True
    if (norm.get("list-unsubscribe-post") or "").strip():
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
    if any(
        kw in subject
        for kw in (
            "price alert",
            "flight alert",
            "price drop",
            "price tracking",
            "calendar invitation",
            "calendar reminder",
            "order confirm",
            "shipping confirm",
            "purchase confirm",
            "receipt for",
            "invoice for",
            "reset your",
            "password reset",
            "verification code",
            "security code",
            "sign-in alert",
            "login alert",
            "new sign-in",
        )
    ):
        return True
    return False


def _bulk_marketing(norm: dict[str, str]) -> bool:
    """Bulk / list mail heuristics (given an unsubscribe path was already found elsewhere)."""
    precedence = (norm.get("precedence") or "").strip().lower()
    if precedence == "bulk":
        return True
    from_ = (norm.get("from") or "").lower()
    if any(h in from_ for h in ("newsletter@", "digest@", "marketing@", "mailer@")):
        return True
    # RFC 2369 List-Unsubscribe — any non-empty value (https, mailto, vendor-specific).
    if (norm.get("list-unsubscribe") or "").strip():
        return True
    # RFC 8058 one-click — strong mailing-list signal.
    if (norm.get("list-unsubscribe-post") or "").strip():
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


def is_digest_source_candidate(
    headers: dict[str, str],
    *,
    has_body_unsubscribe_link: bool = False,
) -> bool:
    """
    True when the message looks like a list / newsletter source the digest may want.

    Uses the same heuristics as :func:`is_unsubscribable_newsletter`; digest vs
    unsubscribe differs at **keep-list** semantics (see project brief), not here.
    """
    return is_unsubscribable_newsletter(
        headers, has_body_unsubscribe_link=has_body_unsubscribe_link
    )
