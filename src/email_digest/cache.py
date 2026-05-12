"""SQLite cache: LLM call log, extractions, embedding slots (M3)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            alias TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cost_usd REAL
        );

        CREATE TABLE IF NOT EXISTS extractions (
            topic TEXT NOT NULL,
            gmail_message_id TEXT NOT NULL,
            json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (topic, gmail_message_id)
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            claim_hash TEXT PRIMARY KEY,
            dim INTEGER NOT NULL,
            vector BLOB NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls(ts);
        """
    )
    conn.commit()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def insert_llm_call(
    conn: sqlite3.Connection,
    *,
    alias: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
    ts: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO llm_calls (ts, alias, model, input_tokens, output_tokens, cost_usd)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ts or _utc_now_iso(), alias, model, input_tokens, output_tokens, cost_usd),
    )
    conn.commit()


def get_extraction_json(
    conn: sqlite3.Connection, topic: str, gmail_message_id: str
) -> str | None:
    row = conn.execute(
        "SELECT json FROM extractions WHERE topic = ? AND gmail_message_id = ?",
        (topic, gmail_message_id),
    ).fetchone()
    return None if row is None else str(row[0])


def put_extraction_json(
    conn: sqlite3.Connection,
    topic: str,
    gmail_message_id: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO extractions (topic, gmail_message_id, json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(topic, gmail_message_id) DO UPDATE SET
            json = excluded.json,
            updated_at = excluded.updated_at
        """,
        (topic, gmail_message_id, json.dumps(payload, sort_keys=True), _utc_now_iso()),
    )
    conn.commit()


def get_embedding_vector(
    conn: sqlite3.Connection, claim_hash: str
) -> np.ndarray | None:
    row = conn.execute(
        "SELECT dim, vector FROM embeddings WHERE claim_hash = ?",
        (claim_hash,),
    ).fetchone()
    if row is None:
        return None
    dim, blob = int(row[0]), row[1]
    return np.frombuffer(blob, dtype=np.float32).copy().reshape(dim)


def put_embedding_vector(
    conn: sqlite3.Connection, claim_hash: str, vec: np.ndarray
) -> None:
    v = np.asarray(vec, dtype=np.float32).reshape(-1)
    conn.execute(
        """
        INSERT INTO embeddings (claim_hash, dim, vector, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(claim_hash) DO UPDATE SET
            dim = excluded.dim,
            vector = excluded.vector,
            updated_at = excluded.updated_at
        """,
        (claim_hash, int(v.shape[0]), v.tobytes(), _utc_now_iso()),
    )
    conn.commit()


@dataclass(frozen=True)
class LlmCostSummary:
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


def summarize_llm_calls(conn: sqlite3.Connection, *, days: int = 7) -> LlmCostSummary:
    cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat()
    row = conn.execute(
        """
        SELECT
            COUNT(*),
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            SUM(cost_usd)
        FROM llm_calls
        WHERE ts >= ?
        """,
        (cutoff,),
    ).fetchone()
    assert row is not None
    n, inp, out, cost_sum = row
    return LlmCostSummary(
        calls=int(n),
        input_tokens=int(inp),
        output_tokens=int(out),
        cost_usd=None if cost_sum is None else float(cost_sum),
    )


def summarize_llm_calls_by_alias(
    conn: sqlite3.Connection, *, days: int = 7
) -> list[dict[str, Any]]:
    """Per-``alias`` rollups for the same rolling window as :func:`summarize_llm_calls`."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat()
    rows = conn.execute(
        """
        SELECT
            alias,
            COUNT(*),
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            SUM(cost_usd)
        FROM llm_calls
        WHERE ts >= ?
        GROUP BY alias
        ORDER BY alias
        """,
        (cutoff,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for alias, n, inp, out_tok, cost_sum in rows:
        out.append(
            {
                "alias": str(alias),
                "calls": int(n),
                "input_tokens": int(inp),
                "output_tokens": int(out_tok),
                "cost_usd": None if cost_sum is None else float(cost_sum),
            }
        )
    return out


def summarize_llm_calls_by_model(
    conn: sqlite3.Connection, *, days: int = 7
) -> list[dict[str, Any]]:
    """Per-``model`` id rollups (same window as :func:`summarize_llm_calls`)."""
    cutoff = (datetime.now(UTC) - timedelta(days=days)).replace(microsecond=0).isoformat()
    rows = conn.execute(
        """
        SELECT
            model,
            COUNT(*),
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            SUM(cost_usd)
        FROM llm_calls
        WHERE ts >= ?
        GROUP BY model
        ORDER BY model
        """,
        (cutoff,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for model, n, inp, out_tok, cost_sum in rows:
        out.append(
            {
                "model": str(model),
                "calls": int(n),
                "input_tokens": int(inp),
                "output_tokens": int(out_tok),
                "cost_usd": None if cost_sum is None else float(cost_sum),
            }
        )
    return out


def format_cost_report(db_path: Path, *, days: int = 7) -> str:
    if not db_path.is_file():
        return f"No digest cache at {db_path} (no LLM calls logged yet).\n"
    conn = connect(db_path)
    try:
        s = summarize_llm_calls(conn, days=days)
        by_alias = summarize_llm_calls_by_alias(conn, days=days)
        by_model = summarize_llm_calls_by_model(conn, days=days)
    finally:
        conn.close()
    cost = "n/a" if s.cost_usd is None else f"{s.cost_usd:.6f}"
    lines = [
        f"LLM calls (last {days} days): {s.calls}\n",
        f"Input tokens:  {s.input_tokens}\n",
        f"Output tokens: {s.output_tokens}\n",
        f"Cost USD (sum): {cost}\n",
    ]
    if by_alias:
        lines.append("By alias:\n")
        for r in by_alias:
            ac = "n/a" if r["cost_usd"] is None else f"{r['cost_usd']:.6f}"
            lines.append(
                f"  {r['alias']}: calls={r['calls']}, "
                f"in={r['input_tokens']}, out={r['output_tokens']}, USD={ac}\n"
            )
    if by_model:
        lines.append("By model:\n")
        for r in by_model:
            mc = "n/a" if r["cost_usd"] is None else f"{r['cost_usd']:.6f}"
            lines.append(
                f"  {r['model']}: calls={r['calls']}, "
                f"in={r['input_tokens']}, out={r['output_tokens']}, USD={mc}\n"
            )
    return "".join(lines)


def cost_report_payload(db_path: Path, *, days: int = 7) -> dict[str, Any]:
    """Structured cost summary for ``digest cost --json`` and automation."""
    base: dict[str, Any] = {
        "cache_db": str(db_path.resolve()),
        "days": int(days),
    }
    if not db_path.is_file():
        return {
            **base,
            "cache_missing": True,
            "calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": None,
            "by_alias": [],
            "by_model": [],
        }
    conn = connect(db_path)
    try:
        s = summarize_llm_calls(conn, days=days)
        by_alias = summarize_llm_calls_by_alias(conn, days=days)
        by_model = summarize_llm_calls_by_model(conn, days=days)
    finally:
        conn.close()
    return {
        **base,
        "cache_missing": False,
        "calls": s.calls,
        "input_tokens": s.input_tokens,
        "output_tokens": s.output_tokens,
        "cost_usd": s.cost_usd,
        "by_alias": by_alias,
        "by_model": by_model,
    }
