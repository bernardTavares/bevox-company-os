"""Tests for tune_suggest.py — weekly analyzer (W8.P6)."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from lib.knowledge_watcher.feedback_db import init_db
from lib.knowledge_watcher.tune_suggest import (
    analyze_tuning_candidates, format_suggestions_for_telegram,
    KEEP_RATIO_THRESHOLD, MIN_N,
)


def _seed_decisions(db_path: Path, doc_type: str, signals_json: str,
                    decision: str, count: int) -> None:
    conn = sqlite3.connect(str(db_path))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i in range(count):
        conn.execute(
            "INSERT INTO decisions "
            "(ts, gap_id, source, doc_type, project_slug, signals_json, decision) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (today, f"g_{doc_type}_{decision}_{i}", "f4", doc_type, "p1",
             signals_json, decision),
        )
    conn.commit()
    conn.close()


def test_no_suggestions_when_under_threshold(tmp_path, monkeypatch):
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    # 50% keep, 50% retire — no tuning candidate
    _seed_decisions(db, "adr", '[{"category":"B_code_broken"}]', "keep", 5)
    _seed_decisions(db, "adr", '[{"category":"B_code_broken"}]', "retire", 5)

    suggestions = analyze_tuning_candidates(days=30)
    assert suggestions == []


def test_suggestion_when_keep_ratio_high(tmp_path, monkeypatch):
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    # 10 keep, 0 retire → keep_ratio = 1.0 → tuning candidate
    _seed_decisions(db, "adr", '[{"category":"B_code_broken"}]', "keep", 10)

    suggestions = analyze_tuning_candidates(days=30)
    assert len(suggestions) == 1
    s = suggestions[0]
    assert s["doc_type"] == "adr"
    assert s["signal_combo"] == "B"
    assert s["keep_ratio"] == 1.0
    assert "/tune adr threshold 1.0" in s["tune_command"]


def test_min_n_filter_blocks_shallow_signal(tmp_path, monkeypatch):
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    # Only 3 keep — below MIN_N=4
    _seed_decisions(db, "adr", '[{"category":"B_code_broken"}]', "keep",
                    MIN_N - 1)
    suggestions = analyze_tuning_candidates(days=30)
    assert suggestions == []


def test_format_telegram_no_suggestions():
    text = format_suggestions_for_telegram([])
    assert "sem suggestions" in text


def test_format_telegram_with_suggestions():
    suggestions = [
        {
            "doc_type": "adr", "signal_combo": "B",
            "n": 12, "keep_ratio": 0.92,
            "suggestion": "...", "tune_command": "/tune adr threshold 1.0",
        }
    ]
    text = format_suggestions_for_telegram(suggestions)
    assert "tuning suggestions" in text
    assert "adr + B" in text
    assert "/tune adr threshold 1.0" in text
