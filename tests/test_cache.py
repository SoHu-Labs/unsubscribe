"""SQLite digest cache."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from email_digest.cache import (
    connect,
    cost_report_payload,
    format_cost_report,
    get_embedding_vector,
    get_extraction_json,
    insert_llm_call,
    put_embedding_vector,
    put_extraction_json,
    summarize_llm_calls,
    summarize_llm_calls_by_alias,
    summarize_llm_calls_by_model,
)


def test_insert_and_summarize_llm_calls(tmp_path: Path) -> None:
    db = tmp_path / "d.sqlite"
    conn = connect(db)
    insert_llm_call(
        conn,
        alias="fast",
        model="deepseek/x",
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.001,
        ts="2099-01-01T00:00:00+00:00",
    )
    insert_llm_call(
        conn,
        alias="fast",
        model="deepseek/x",
        input_tokens=1,
        output_tokens=2,
        cost_usd=0.0001,
        ts="2020-01-01T00:00:00+00:00",
    )
    s = summarize_llm_calls(conn, days=7)
    conn.close()
    assert s.calls == 1
    assert s.input_tokens == 10
    assert s.output_tokens == 20
    assert s.cost_usd is not None and abs(s.cost_usd - 0.001) < 1e-9


def test_summarize_llm_calls_by_alias_groups(tmp_path: Path) -> None:
    db = tmp_path / "by.sqlite"
    conn = connect(db)
    insert_llm_call(
        conn,
        alias="fast",
        model="m",
        input_tokens=10,
        output_tokens=1,
        cost_usd=0.001,
        ts="2099-03-01T00:00:00+00:00",
    )
    insert_llm_call(
        conn,
        alias="smart",
        model="m",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.05,
        ts="2099-03-02T00:00:00+00:00",
    )
    insert_llm_call(
        conn,
        alias="fast",
        model="m",
        input_tokens=5,
        output_tokens=2,
        cost_usd=0.002,
        ts="2099-03-03T00:00:00+00:00",
    )
    rows = summarize_llm_calls_by_alias(conn, days=30)
    conn.close()
    assert [r["alias"] for r in rows] == ["fast", "smart"]
    fast = next(r for r in rows if r["alias"] == "fast")
    assert fast["calls"] == 2
    assert fast["input_tokens"] == 15
    assert fast["output_tokens"] == 3
    assert fast["cost_usd"] is not None and abs(fast["cost_usd"] - 0.003) < 1e-9


def test_format_cost_report_missing_file(tmp_path: Path) -> None:
    text = format_cost_report(tmp_path / "nope.sqlite", days=7)
    assert "No digest cache" in text


def test_cost_report_payload_missing_file(tmp_path: Path) -> None:
    p = tmp_path / "gone.sqlite"
    d = cost_report_payload(p, days=14)
    assert d["cache_missing"] is True
    assert d["days"] == 14
    assert d["calls"] == 0
    assert d["cache_db"] == str(p.resolve())
    assert d["by_alias"] == []
    assert d["by_model"] == []


def test_cost_report_payload_with_rows(tmp_path: Path) -> None:
    db = tmp_path / "c.sqlite"
    conn = connect(db)
    insert_llm_call(
        conn,
        alias="fast",
        model="m",
        input_tokens=5,
        output_tokens=5,
        cost_usd=0.01,
        ts="2099-06-01T12:00:00+00:00",
    )
    conn.close()
    d = cost_report_payload(db, days=30)
    assert d["cache_missing"] is False
    assert d["calls"] == 1
    assert d["input_tokens"] == 5
    assert d["output_tokens"] == 5
    assert d["cost_usd"] is not None and abs(d["cost_usd"] - 0.01) < 1e-9
    assert d["by_alias"] == [
        {
            "alias": "fast",
            "calls": 1,
            "input_tokens": 5,
            "output_tokens": 5,
            "cost_usd": 0.01,
        }
    ]
    assert d["by_model"] == [
        {
            "model": "m",
            "calls": 1,
            "input_tokens": 5,
            "output_tokens": 5,
            "cost_usd": 0.01,
        }
    ]


def test_summarize_llm_calls_by_model_groups(tmp_path: Path) -> None:
    db = tmp_path / "bm.sqlite"
    conn = connect(db)
    insert_llm_call(
        conn,
        alias="fast",
        model="deepseek/a",
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.001,
        ts="2099-04-01T00:00:00+00:00",
    )
    insert_llm_call(
        conn,
        alias="smart",
        model="deepseek/b",
        input_tokens=2,
        output_tokens=2,
        cost_usd=0.002,
        ts="2099-04-02T00:00:00+00:00",
    )
    insert_llm_call(
        conn,
        alias="fast",
        model="deepseek/a",
        input_tokens=3,
        output_tokens=3,
        cost_usd=0.003,
        ts="2099-04-03T00:00:00+00:00",
    )
    rows = summarize_llm_calls_by_model(conn, days=30)
    conn.close()
    assert [r["model"] for r in rows] == ["deepseek/a", "deepseek/b"]
    a = next(r for r in rows if r["model"] == "deepseek/a")
    assert a["calls"] == 2
    assert a["input_tokens"] == 4


def test_format_cost_report_includes_by_alias(tmp_path: Path) -> None:
    db = tmp_path / "fmt.sqlite"
    conn = connect(db)
    insert_llm_call(
        conn,
        alias="smart",
        model="m",
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.1,
        ts="2099-08-01T00:00:00+00:00",
    )
    conn.close()
    text = format_cost_report(db, days=7)
    assert "By alias:" in text
    assert "smart:" in text
    assert "By model:" in text
    assert "m:" in text


def test_extraction_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "d.sqlite"
    conn = connect(db)
    put_extraction_json(conn, "ai", "mid1", {"key_claims": ["a"]})
    raw = get_extraction_json(conn, "ai", "mid1")
    conn.close()
    assert raw is not None and "key_claims" in raw


def test_embedding_vector_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "emb.sqlite"
    conn = connect(db)
    v = np.array([0.25, 0.5, 1.0], dtype=np.float32)
    put_embedding_vector(conn, "abc", v)
    got = get_embedding_vector(conn, "abc")
    conn.close()
    assert got is not None
    assert np.allclose(got, v)
