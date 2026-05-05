"""Shared visible-text markers for unsubscribe outcomes and preference-center pages."""

from __future__ import annotations

# Lowercased substring match against page text.
CONFIRMATION_TEXT_MARKERS: tuple[str, ...] = (
    "you have been unsubscribed",
    "you've been unsubscribed",
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
