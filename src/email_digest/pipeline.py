"""Digest orchestration: collect, extract, trending, synthesis, HTML (M4)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from unsubscribe.gmail_api_backend import strip_html_to_text
from unsubscribe.gmail_facade import GmailFacade
from unsubscribe.keep_list import load_keep_list, sender_key

from email_digest.cache import connect, get_extraction_json, put_extraction_json
from email_digest.config import TopicConfig
from email_digest.digest_mail import maybe_email_digest
from email_digest.gmail_query import build_digest_gmail_query
from email_digest.llm import complete as llm_complete
from email_digest.paths import default_cache_db_path, repo_root

_EXTRACTION_SYSTEM = (
    "You extract structured information from a single email. "
    "Reply with one JSON object only, no markdown fences."
)
_MAX_BODY_CHARS = 12_000


def _append_per_message_failure_log(
    *,
    output_root: Path,
    run_day_iso: str,
    topic: str,
    message_id: str,
    exc: BaseException,
) -> None:
    """Append one line to ``output/_failures/<run_day_iso>.log`` (project brief: no silent drops)."""
    failures_dir = output_root / "_failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    log_path = failures_dir / f"{run_day_iso}.log"
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts}\t{topic}\t{message_id}\t{type(exc).__name__}\t{exc}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def _extraction_user_message(subject: str, body: str) -> str:
    return (
        "Email subject:\n"
        f"{subject}\n\n"
        "Email body (plain text, may be truncated):\n"
        f"{body}\n\n"
        "Extract structured data. Output JSON with keys "
        "key_claims (array of 5-10 short strings), entities (array of strings), "
        "numbers (array of strings or numbers). Use empty arrays when nothing applies."
    )


def _compute_trending(
    cfg: TopicConfig,
    out_messages: list[dict[str, Any]],
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for msg in out_messages:
        ext = msg.get("extraction")
        if not isinstance(ext, dict):
            continue
        kc = ext.get("key_claims")
        if not isinstance(kc, list):
            continue
        for j, raw in enumerate(kc):
            if isinstance(raw, str) and raw.strip():
                claims.append(
                    {
                        "message_id": msg["id"],
                        "claim_index": j,
                        "text": raw.strip(),
                    }
                )
    if len(claims) < cfg.trending_min_cluster_size:
        return []

    from email_digest.cluster import (
        cluster_labels,
        filter_clusters_by_cohesion,
        trending_clusters,
    )
    from email_digest.embed import embed_claim_texts

    texts = [str(c["text"]) for c in claims]
    mat = embed_claim_texts(texts, conn=conn)
    labs = cluster_labels(
        mat,
        min_cluster_size=cfg.trending_min_cluster_size,
        algorithm=cfg.trending_algorithm,
    )
    labs = filter_clusters_by_cohesion(
        mat,
        labs,
        min_mean_cosine=cfg.trending_similarity_threshold,
    )
    return trending_clusters(claims, labs)


def run_digest(
    cfg: TopicConfig,
    *,
    facade: GmailFacade,
    keep_list_path: Path,
    max_results: int = 50,
    since: date | None = None,
    cache_db: Path | None = None,
    dry_run: bool = True,
    output_dir: Path | None = None,
    template_dir: Path | None = None,
) -> dict[str, Any]:
    query = build_digest_gmail_query(
        window_days=cfg.window_days,
        senders=list(cfg.senders),
        folders=list(cfg.folders),
        since=since,
    )
    rows = facade.list_messages(query, max_results=max_results)
    keep = load_keep_list(keep_list_path)

    db_path = cache_db or default_cache_db_path()
    conn = connect(db_path)

    out_messages: list[dict[str, Any]] = []
    trending: list[dict[str, Any]] = []
    output_dir = output_dir or (repo_root() / "output")
    run_day_iso = datetime.now(UTC).date().isoformat()
    try:
        for m in rows:
            sk = sender_key(m.from_)
            if sk is None or sk not in keep:
                continue
            try:
                cached = get_extraction_json(conn, cfg.name, m.id)
                if cached is not None:
                    try:
                        extraction = json.loads(cached)
                    except json.JSONDecodeError:
                        extraction = {"parse_error": True, "raw": cached[:2000]}
                else:
                    html = facade.get_message_html(m.id)
                    plain = strip_html_to_text(html)[:_MAX_BODY_CHARS]
                    user = _extraction_user_message(m.subject, plain)
                    raw = llm_complete(
                        [
                            {"role": "system", "content": _EXTRACTION_SYSTEM},
                            {"role": "user", "content": user},
                        ],
                        alias=cfg.extract_model,
                        json_mode=True,
                    )
                    try:
                        extraction = json.loads(raw)
                    except json.JSONDecodeError:
                        extraction = {"parse_error": True, "raw": raw[:2000]}
                    else:
                        put_extraction_json(conn, cfg.name, m.id, extraction)
                out_messages.append(
                    {
                        "id": m.id,
                        "rfc_message_id": m.rfc_message_id,
                        "from": m.from_,
                        "subject": m.subject,
                        "date": m.date,
                        "extraction": extraction,
                    }
                )
            except Exception as exc:
                _append_per_message_failure_log(
                    output_root=output_dir,
                    run_day_iso=run_day_iso,
                    topic=cfg.name,
                    message_id=m.id,
                    exc=exc,
                )
        trending = _compute_trending(cfg, out_messages, conn)
    finally:
        conn.close()

    base: dict[str, Any] = {
        "topic": cfg.name,
        "query": query,
        "messages": out_messages,
        "trending": trending,
    }
    if dry_run:
        return base

    from email_digest.render import render_digest_html
    from email_digest.synthesis import synthesize_digest

    synth = synthesize_digest(cfg, base)
    td = template_dir or (repo_root() / "templates")
    output_dir.mkdir(parents=True, exist_ok=True)
    html = render_digest_html(
        cfg=cfg,
        synthesis=synth,
        messages=out_messages,
        template_dir=td,
    )
    path = output_dir / f"{cfg.name}_{run_day_iso}.html"
    path.write_text(html, encoding="utf-8")
    emailed_to: str | None = None
    if cfg.also_email_to:
        emailed_to = maybe_email_digest(cfg, html, date_iso=run_day_iso, facade=facade)
    return {
        **base,
        "synthesis": synth,
        "output_html": str(path),
        "emailed_to": emailed_to,
    }


def run_digest_dry_run(
    cfg: TopicConfig,
    *,
    facade: GmailFacade,
    keep_list_path: Path,
    max_results: int = 50,
    since: date | None = None,
    cache_db: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Collect + extract + trending; JSON-shaped result (no synthesis / no HTML file)."""
    return run_digest(
        cfg,
        facade=facade,
        keep_list_path=keep_list_path,
        max_results=max_results,
        since=since,
        cache_db=cache_db,
        dry_run=True,
        output_dir=output_dir,
    )
