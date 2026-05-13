"""Topic-scoped terminal walkthrough: add digest sources to the shared keep list."""

from __future__ import annotations

import sys
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date
from pathlib import Path

from unsubscribe.classifier import is_digest_source_candidate
from unsubscribe.gmail_facade import GmailFacade, headers_from_summary
from unsubscribe.keep_list import add_to_keep_list, is_kept, load_keep_list

from email_digest.config import TopicConfig
from email_digest.gmail_query import build_digest_gmail_query

_BODY_PREFETCH_WORKERS = 8
_PREVIEW_WIDTH = 72
_PREVIEW_MAX_LINES = 5


def _body_preview_lines(
    text: str,
    *,
    width: int = _PREVIEW_WIDTH,
    max_lines: int = _PREVIEW_MAX_LINES,
) -> str:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        cand = " ".join(cur + [w])
        if len(cand) > width and cur:
            lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines:
                break
        else:
            cur.append(w)
    if len(lines) < max_lines and cur:
        lines.append(" ".join(cur))
    return "\n".join(lines[:max_lines])


def _fetch_one_body_plain(facade: GmailFacade, message_id: str) -> str:
    try:
        return facade.get_message_body_text(message_id)
    except Exception as e:
        print(f"(Could not load body for {message_id}: {e})", file=sys.stderr, flush=True)
        return ""


def _start_body_prefetch(
    facade: GmailFacade,
    messages: list,
) -> tuple[ThreadPoolExecutor, dict[str, Future[str]]]:
    n = len(messages)
    workers = min(_BODY_PREFETCH_WORKERS, max(1, n))
    executor = ThreadPoolExecutor(max_workers=workers)
    futures: dict[str, Future[str]] = {
        m.id: executor.submit(_fetch_one_body_plain, facade, m.id) for m in messages
    }
    return executor, futures


def _prompt_keep_skip_quit(prompt: str, *, input_fn: Callable[[str], str]) -> str:
    """Return ``''`` (keep), ``'s'`` (skip), or ``'q'`` (quit)."""
    while True:
        raw = input_fn(prompt)
        s = raw.strip().lower()
        if s == "":
            return ""
        if s == "s":
            return "s"
        if s == "q":
            return "q"
        print("  (Enter = keep, s = skip, q = quit — try again.)", flush=True)


def run_digest_walkthrough(
    cfg: TopicConfig,
    topic_path: Path,
    facade: GmailFacade,
    keep_list_path: Path,
    *,
    since: date | None,
    max_results: int,
    input_fn: Callable[[str], str],
    body: bool = False,
) -> int:
    """Interactive review of digest-source candidates for one topic; mutates keep file on [Enter].

    Returns ``0`` on normal completion, ``1`` if Gmail list fails, ``130`` on interrupt
    (matching ``unsubscribe check``).  When *body* is True, plain-text bodies are
    prefetched in parallel and shown as a preview for each non-kept candidate.
    """
    query = build_digest_gmail_query(
        window_days=cfg.window_days,
        senders=list(cfg.senders),
        folders=list(cfg.folders),
        since=since,
    )
    print(
        f"Digest walkthrough — topic {cfg.name!r} (file {topic_path.name})\n"
        f"Query: {query}\n"
        "Only messages classified as digest-source candidates are shown "
        "(same heuristic as ``digest candidates``).",
        flush=True,
    )
    try:
        messages = facade.list_messages(query, max_results=max_results)
    except Exception as e:
        print(f"Could not list messages: {e}", file=sys.stderr, flush=True)
        return 1

    filtered = [
        m for m in messages if is_digest_source_candidate(headers_from_summary(m))
    ]
    if not filtered:
        print("\nNo digest-source candidates in this query window.", flush=True)
        return 0

    print(f"\n{len(filtered)} candidate(s).", flush=True)

    body_pool: ThreadPoolExecutor | None = None
    body_futures: dict[str, Future[str]] = {}
    if body:
        keep_pre = load_keep_list(keep_list_path)
        prefetch = [m for m in filtered if not is_kept(keep_pre, m.from_)]
        if prefetch:
            body_pool, body_futures = _start_body_prefetch(facade, prefetch)

    try:
        for i, m in enumerate(filtered, start=1):
            keep_data = load_keep_list(keep_list_path)
            if is_kept(keep_data, m.from_):
                print(
                    f"\n{'─' * 60}\n  #{i}  (already in keep list — skipping)\n"
                    f"  From: {m.from_}\n  Subject: {m.subject!r}\n",
                    flush=True,
                )
                continue
            print(
                f"\n{'─' * 60}\n  #{i}  From: {m.from_}\n"
                f"  Subject: {m.subject!r}\n  Date: {m.date}\n",
                end="",
                flush=True,
            )
            if body and m.id in body_futures:
                body_text = body_futures[m.id].result()
                if body_text:
                    print(_body_preview_lines(body_text), flush=True)
                else:
                    print("(no preview)", flush=True)
                print(flush=True)
            action = _prompt_keep_skip_quit(
                "  [Enter] add sender to keep list (digest source)  "
                "[s] skip  [q] quit walkthrough\n  > ",
                input_fn=input_fn,
            )
            if action == "":
                add_to_keep_list(keep_list_path, m.from_, m.subject)
                print("  (saved to keep list.)", flush=True)
            elif action == "s":
                print("  (skipped.)", flush=True)
            else:
                print(
                    "\n(Stopping walkthrough early; prior [Enter] saves are already on disk.)",
                    flush=True,
                )
                break
    except KeyboardInterrupt:
        print("\nInterrupted. Partial [Enter] saves are already on disk.", flush=True)
        return 130
    finally:
        if body_pool is not None:
            body_pool.shutdown(wait=False, cancel_futures=True)

    print("\nWalkthrough finished.", flush=True)
    return 0
