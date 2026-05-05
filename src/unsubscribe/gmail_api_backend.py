"""Gmail API read path (``users.messages.list`` / ``get``) using OAuth token file from disk."""

from __future__ import annotations

import base64
import os
import re
from html import unescape
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from unsubscribe.gmail_facade import GmailHeaderSummary, GmailTransportError

_ENV_OAUTH_TOKEN = "GOOGLE_OAUTH_TOKEN"

_SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)

_METADATA_HEADERS = (
    "List-Unsubscribe",
    "List-Unsubscribe-Post",
    "Subject",
    "From",
    "Date",
)

_MAX_BODY_TEXT_CHARS = 500


def _urlsafe_b64decode(data: str) -> bytes:
    pad = (4 - len(data) % 4) % 4
    return base64.urlsafe_b64decode(data + ("=" * pad))


def _raw_from_part_body(part: dict) -> str | None:
    body = part.get("body") or {}
    raw = body.get("data")
    if not raw:
        return None
    try:
        return _urlsafe_b64decode(raw).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return None


def html_from_gmail_message_payload(payload: dict) -> str | None:
    """First ``text/html`` body in a Gmail API ``payload`` tree, or ``None``."""
    if (payload.get("mimeType") or "").lower() == "text/html":
        h = _raw_from_part_body(payload)
        if h:
            return h
    for part in payload.get("parts") or []:
        mt = (part.get("mimeType") or "").lower()
        if mt == "text/html":
            html = _raw_from_part_body(part)
            if html:
                return html
        nested = html_from_gmail_message_payload(part)
        if nested:
            return nested
    return None


def plaintext_from_gmail_message_payload(payload: dict) -> str | None:
    """First ``text/plain`` body in a Gmail API ``payload`` tree, or ``None``."""
    if (payload.get("mimeType") or "").lower() == "text/plain":
        t = _raw_from_part_body(payload)
        if t:
            return t
    for part in payload.get("parts") or []:
        mt = (part.get("mimeType") or "").lower()
        if mt == "text/plain":
            text = _raw_from_part_body(part)
            if text:
                return text
        nested = plaintext_from_gmail_message_payload(part)
        if nested:
            return nested
    return None


def strip_html_to_text(html: str) -> str:
    """Best-effort HTML → single-line plain text (no external deps)."""
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class GmailApiBackend:
    """Gmail API backend: read via OAuth token file (``gmail.readonly`` only)."""

    def __init__(self, *, credentials: Credentials) -> None:
        self._credentials = credentials

    @classmethod
    def from_token_path(cls, path: Path) -> GmailApiBackend:
        p = path.expanduser()
        if not p.is_file():
            raise ValueError(f"OAuth token path is not a file: {p}")
        creds = Credentials.from_authorized_user_file(str(p), scopes=_SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                try:
                    from google.auth.transport.requests import Request

                    creds.refresh(Request())
                except Exception as e:
                    raise ValueError(
                        f"Could not refresh OAuth token ({p}): {e}"
                    ) from e
            else:
                raise ValueError(
                    f"OAuth token missing or invalid ({p}); re-authorize with gmail.readonly scope."
                )
        return cls(credentials=creds)

    @classmethod
    def from_env(cls) -> GmailApiBackend:
        raw = os.environ.get(_ENV_OAUTH_TOKEN, "").strip()
        if not raw:
            raise ValueError(
                f"Set {_ENV_OAUTH_TOKEN} to the authorized-user JSON file from your OAuth flow "
                "(must include gmail.readonly)."
            )
        return cls.from_token_path(Path(raw))

    def _service(self):
        return build("gmail", "v1", credentials=self._credentials, cache_discovery=False)

    def list_messages(self, query: str, *, max_results: int = 10) -> list[GmailHeaderSummary]:
        if max_results < 1:
            raise ValueError("max_results must be at least 1")
        try:
            service = self._service()
            list_resp = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            raw_msgs = list_resp.get("messages") or []
            out: list[GmailHeaderSummary] = []
            get_api = service.users().messages().get
            for m in raw_msgs:
                mid = m["id"]
                tid = m.get("threadId", "")

                meta = get_api(
                    userId="me",
                    id=mid,
                    format="metadata",
                    metadataHeaders=list(_METADATA_HEADERS),
                ).execute()
                headers = {
                    h["name"]: h["value"]
                    for h in (meta.get("payload", {}).get("headers") or [])
                }

                minimal = get_api(
                    userId="me",
                    id=mid,
                    format="minimal",
                ).execute()

                out.append(
                    GmailHeaderSummary(
                        id=mid,
                        thread_id=meta.get("threadId", tid),
                        from_=headers.get("From", ""),
                        subject=headers.get("Subject", ""),
                        date=headers.get("Date", ""),
                        snippet=minimal.get("snippet", ""),
                        list_unsubscribe=headers.get("List-Unsubscribe"),
                        list_unsubscribe_post=headers.get("List-Unsubscribe-Post"),
                    )
                )
            return out
        except HttpError as e:
            raise GmailTransportError(f"Gmail API error: {e}") from e

    def get_message_html(self, message_id: str) -> str:
        """Fetch ``format=full`` and return the first ``text/html`` body."""
        try:
            service = self._service()
            full = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            payload = full.get("payload") or {}
            html = html_from_gmail_message_payload(payload)
            if not html:
                raise GmailTransportError(
                    f"No text/html part in Gmail message {message_id!r}."
                )
            return html
        except HttpError as e:
            raise GmailTransportError(f"Gmail API error: {e}") from e

    def get_message_body_text(self, message_id: str) -> str:
        """Plain text for previews: HTML stripped when present, else first ``text/plain``."""
        try:
            service = self._service()
            full = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            payload = full.get("payload") or {}
            html = html_from_gmail_message_payload(payload)
            if html:
                text = strip_html_to_text(html)
            else:
                text = (plaintext_from_gmail_message_payload(payload) or "").strip()
            if len(text) > _MAX_BODY_TEXT_CHARS:
                text = text[:_MAX_BODY_TEXT_CHARS]
            return text
        except HttpError as e:
            raise GmailTransportError(f"Gmail API error: {e}") from e
