"""Shared visible-text markers for unsubscribe outcomes and preference-center pages."""

from __future__ import annotations


def normalize_text_for_confirmation_match(text: str) -> str:
    """Lowercase and fold typographic quotes so substring markers match DOM copy."""

    t = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    return t.replace("\u201c", '"').replace("\u201d", '"')


# Lowercased substring match after :func:`normalize_text_for_confirmation_match`.
CONFIRMATION_TEXT_MARKERS: tuple[str, ...] = (
    "you have been unsubscribed",
    "you've been unsubscribed",
    "you've unsubscribed",
    "you'll no longer receive",
    "successfully unsubscribed",
    "unsubscribed successfully",
    "you are unsubscribed",
    "we unsubscribed you",
    "your email has been removed",
    "removed from our mailing list",
    "you will no longer receive",
    "successfully removed from this subscriber list",
    "won't receive any further emails",
    "will not receive any further emails",
)

# Preference-center multi-step hints (lowercased substring).
PREFERENCE_CENTER_SNIPPETS: tuple[str, ...] = (
    "unsubscribe from all",
    "unsubscribe from all lists",
    "unsubscribe me from all",
)
