"""Gmail operations behind a pluggable backend (use mocks/fakes in tests; real HTTP later)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class GmailHeaderSummary:
    """Row for inbox search results (headers + snippet from metadata/minimal pair)."""

    id: str
    thread_id: str
    from_: str
    subject: str
    date: str
    snippet: str
    list_unsubscribe: str | None
    list_unsubscribe_post: str | None
    #: Mailbox that received the message (``Delivered-To`` / ``To``), for form prefills.
    delivered_to: str | None = None


def headers_from_summary(m: GmailHeaderSummary) -> dict[str, str]:
    """Build header dict for classification / one-click (omit absent fields)."""
    h: dict[str, str] = {}
    if m.from_:
        h["From"] = m.from_
    if m.subject:
        h["Subject"] = m.subject
    if m.date:
        h["Date"] = m.date
    if m.list_unsubscribe:
        h["List-Unsubscribe"] = m.list_unsubscribe
    if m.list_unsubscribe_post:
        h["List-Unsubscribe-Post"] = m.list_unsubscribe_post
    return h


class GmailTransportError(RuntimeError):
    """Raised when listing or reading message bodies fails at the backend/transport layer."""


@runtime_checkable
class GmailBackend(Protocol):
    def list_messages(
        self, query: str, *, max_results: int = 10
    ) -> list[GmailHeaderSummary]:
        """Return messages for a Gmail search query (`q` string)."""
        ...

    def get_message_html(self, message_id: str) -> str:
        """Return raw ``text/html`` body."""
        ...

    def get_message_body_text(self, message_id: str) -> str:
        """Return plain text (HTML stripped), up to 500 characters."""
        ...


class GmailFacade:
    """Thin façade: stable call shape + consistent error wrapping for orchestration code."""

    def __init__(self, backend: GmailBackend) -> None:
        self._backend = backend

    def list_messages(
        self, query: str, *, max_results: int = 10
    ) -> list[GmailHeaderSummary]:
        try:
            return self._backend.list_messages(query, max_results=max_results)
        except GmailTransportError:
            raise
        except Exception as e:
            raise GmailTransportError(str(e)) from e

    def get_message_html(self, message_id: str) -> str:
        try:
            return self._backend.get_message_html(message_id)
        except GmailTransportError:
            raise
        except Exception as e:
            raise GmailTransportError(str(e)) from e

    def get_message_body_text(self, message_id: str) -> str:
        try:
            return self._backend.get_message_body_text(message_id)
        except GmailTransportError:
            raise
        except Exception as e:
            raise GmailTransportError(str(e)) from e
