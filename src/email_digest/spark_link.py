"""Spark ``readdle-spark://`` deep-links from RFC822 ``Message-ID``."""

from __future__ import annotations

from urllib.parse import quote


def spark_deeplink(rfc_message_id: str) -> str:
    """Return ``readdle-spark://openmessage?messageId=…`` with URL-encoded *rfc_message_id*."""
    mid = (rfc_message_id or "").strip()
    if not mid:
        return ""
    return f"readdle-spark://openmessage?messageId={quote(mid, safe='')}"
