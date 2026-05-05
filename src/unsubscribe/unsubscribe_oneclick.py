"""RFC 2369 List-Unsubscribe parsing and RFC 8058 one-click POST."""

from __future__ import annotations

import urllib.request


class OneClickUnsubscribeError(Exception):
    """Base class for one-click unsubscribe failures."""


class NoUnsubscribeHeaderError(OneClickUnsubscribeError):
    """Message has no parseable ``List-Unsubscribe`` header value."""


class UnsubscribeNotOneClickError(OneClickUnsubscribeError):
    """Sender did not advertise RFC 8058 one-click (or no usable HTTPS target)."""


class UnsubscribePostRedirectError(OneClickUnsubscribeError):
    """POST was answered with a redirect; redirects are not followed."""

    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        detail = f" {message}" if message else ""
        super().__init__(
            f"Unsubscribe POST returned redirect HTTP {status_code}{detail}; not following."
        )


_ONE_CLICK_POST_TOKEN = "list-unsubscribe=one-click"

_BODY_DATA = b"List-Unsubscribe=One-Click"


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, hdrs):  # noqa: ARG002
        raise UnsubscribePostRedirectError(code, msg or "")

    def http_error_302(self, req, fp, code, msg, hdrs):  # noqa: ARG002
        raise UnsubscribePostRedirectError(code, msg or "")

    def http_error_303(self, req, fp, code, msg, hdrs):  # noqa: ARG002
        raise UnsubscribePostRedirectError(code, msg or "")

    def http_error_307(self, req, fp, code, msg, hdrs):  # noqa: ARG002
        raise UnsubscribePostRedirectError(code, msg or "")

    def http_error_308(self, req, fp, code, msg, hdrs):  # noqa: ARG002
        raise UnsubscribePostRedirectError(code, msg or "")


def _urlopen_no_redirect(
    request: urllib.request.Request, *, timeout: float | None = 30
) -> urllib.response.addinfourl:
    opener = urllib.request.build_opener(_RejectRedirects())
    return opener.open(request, timeout=timeout)


def _header_ci(headers: dict[str, str], name: str) -> str | None:
    needle = name.lower()
    for key, val in headers.items():
        if key.lower() == needle:
            return val
    return None


def _is_one_click_post(value: str | None) -> bool:
    if value is None:
        return False
    return _ONE_CLICK_POST_TOKEN in value.replace(" ", "").lower()


def parse_list_unsubscribe(header_value: str) -> list[str]:
    """
    Parse a ``List-Unsubscribe`` header into cleaned ``https`` / ``http`` / ``mailto`` URIs.

    Handles comma-separated lists, optional angle brackets, and folded whitespace.
    Unrecognized tokens are skipped.
    """
    raw = header_value.replace("\r\n", " ").replace("\n", " ").strip()
    if not raw:
        return []

    parts = [p.strip() for p in raw.split(",")]
    out: list[str] = []
    for part in parts:
        token = part.strip()
        if len(token) >= 2 and token[0] == "<" and token[-1] == ">":
            token = token[1:-1].strip()
        if not token:
            continue
        lower = token.lower()
        if lower.startswith("https://"):
            out.append("https://" + token[len("https://") :])
        elif lower.startswith("http://"):
            out.append("http://" + token[len("http://") :])
        elif lower.startswith("mailto:"):
            out.append("mailto:" + token[len("mailto:") :])
    return out


def _mailto_hint(uri: str) -> str:
    rest = uri[len("mailto:") :] if uri.lower().startswith("mailto:") else uri
    addr = rest.split("?", 1)[0].strip()
    return addr or rest


def try_one_click_unsubscribe(
    headers: dict[str, str],
    *,
    post_body: bytes = _BODY_DATA,
    timeout: float | None = 30,
) -> str:
    """
    If RFC 8058 one-click is advertised, POST to the first ``https`` URI in
    ``List-Unsubscribe`` and return a short success summary.

    If one-click is advertised but only ``mailto`` targets exist, return a manual-action
    message (no mail is sent). Missing / malformed headers raise typed errors.
    """
    raw = _header_ci(headers, "List-Unsubscribe")
    if raw is None or not raw.strip():
        raise NoUnsubscribeHeaderError("Missing List-Unsubscribe header.")

    post_hdr = _header_ci(headers, "List-Unsubscribe-Post")
    if not _is_one_click_post(post_hdr):
        raise UnsubscribeNotOneClickError(
            "List-Unsubscribe-Post does not advertise RFC 8058 one-click."
        )

    entries = parse_list_unsubscribe(raw)
    if not entries:
        raise NoUnsubscribeHeaderError("List-Unsubscribe contained no usable URIs.")

    https_urls = [e for e in entries if e.lower().startswith("https://")]
    if https_urls:
        target = https_urls[0]
        req = urllib.request.Request(
            target,
            data=post_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with _urlopen_no_redirect(req, timeout=timeout) as resp:
            code = resp.getcode()
        return f"One-Click unsubscribe accepted (HTTP {code})."

    mailtos = [e for e in entries if e.lower().startswith("mailto:")]
    if mailtos:
        hint = _mailto_hint(mailtos[0])
        return (
            "Manual action required: send email to unsubscribe "
            f"(mailto target: {hint})."
        )

    raise UnsubscribeNotOneClickError(
        "No HTTPS List-Unsubscribe URI for one-click POST (http-only or unrecognized)."
    )
