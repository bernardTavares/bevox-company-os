"""Tests for feedback_stats.py — aggregated queries (W8.P4.T4.1)."""
import json
from datetime import datetime, timezone
import sqlite3
from pathlib import Path

import pytest

from lib.knowledge_watcher.feedback_db import init_db


def _setup_db_with_data(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    conn = sqlite3.connect(str(db))
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = [
        # ADR: 4 keep, 1 retire, 1 keep_permanent
        ("g1", "f4", "adr", "p1", '[{"category":"B_code_broken"}]', "keep"),
        ("g2", "f4", "adr", "p1", '[{"category":"B_code_broken"}]', "keep"),
        ("g3", "f4", "adr", "p2", '[{"category":"B_code_broken"}]', "keep"),
        ("g4", "f4", "adr", "p2", '[{"category":"B_code_broken"}]', "keep"),
        ("g5", "f4", "adr", "p1", '[{"category":"A_markers"}]', "retire"),
        ("g6", "f4", "adr", "p1", '[{"category":"B_code_broken"}]',
         "keep_permanent"),
        # spec: 1 keep, 3 retire (different signals)
        ("g7", "f4", "spec", "p1", '[{"category":"B_code_broken"}]', "keep"),
        ("g8", "f4", "spec", "p1",
         '[{"category":"B_code_broken"},{"category":"E_orphan"}]', "retire"),
        ("g9", "f4", "spec", "p1",
         '[{"category":"B_code_broken"},{"category":"E_orphan"}]', "retire"),
        ("g10", "f4", "spec", "p1",
         '[{"category":"B_code_broken"},{"category":"E_orphan"}]', "retire"),
    ]
    for r in rows:
        conn.execute(
            "INSERT INTO decisions "
            "(ts, gap_id, source, doc_type, project_slug, signals_json, decision) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (today,) + r,
        )
    # F3 outputs
    conn.execute(
        "INSERT INTO f3_outputs "
        "(ts, doc_path, generator, prompt_hash, content_initial_sha, "
        " content_initial, cost_usd, edit_distance_ratio, accepted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (today, "30_adr/p/x.md", "adr", "h", "s", "c", 0.10, 0.10, today),
    )
    conn.execute(
        "INSERT INTO f3_outputs "
        "(ts, doc_path, generator, prompt_hash, content_initial_sha, "
        " content_initial, cost_usd, edit_distance_ratio, accepted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (today, "30_adr/p/y.md", "adr", "h", "s", "c", 0.05, 0.30, today),
    )
    conn.execute(
        "INSERT INTO f3_outputs "
        "(ts, doc_path, generator, prompt_hash, content_initial_sha, "
        " content_initial, cost_usd, edit_distance_ratio, accepted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (today, "10_prd/p/z.md", "prd", "h", "s", "c", 0.05, 0.50, today),
    )
    conn.commit()
    conn.close()
    return db


def test_stats_by_doc_type(tmp_path, monkeypatch):
    _setup_db_with_data(tmp_path, monkeypatch)
    from lib.knowledge_watcher.feedback_stats import stats_by_doc_type
    rows = stats_by_doc_type(days=30)
    by_type = {r["doc_type"]: r for r in rows}
    assert by_type["adr"]["n"] == 6
    assert by_type["adr"]["keep_ratio"] == round(4/6, 3)
    assert by_type["spec"]["n"] == 4
    assert by_type["spec"]["retire_ratio"] == 0.75


def test_stats_by_signal_combo(tmp_path, monkeypatch):
    _setup_db_with_data(tmp_path, monkeypatch)
    from lib.knowledge_watcher.feedback_stats import stats_by_signal_combo
    rows = stats_by_signal_combo(days=30, min_n=1)
    keys = {(r["doc_type"], r["signal_combo"]) for r in rows}
    assert ("adr", "B") in keys  # B alone, mostly keep
    assert ("spec", "B+E") in keys  # B+E, mostly retire


def test_stats_f3_edit_distance(tmp_path, monkeypatch):
    _setup_db_with_data(tmp_path, monkeypatch)
    from lib.knowledge_watcher.feedback_stats import stats_f3_edit_distance
    rows = stats_f3_edit_distance(days=30)
    by_gen = {r["generator"]: r for r in rows}
    assert by_gen["adr"]["n"] == 2
    assert 0.0 < by_gen["adr"]["mean"] < 1.0
    assert by_gen["prd"]["n"] == 1


def test_stats_handles_empty(tmp_path, monkeypatch):
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    from lib.knowledge_watcher.feedback_stats import (
        stats_by_doc_type, stats_f3_edit_distance, stats_by_signal_combo,
    )
    assert stats_by_doc_type(30) == []
    assert stats_f3_edit_distance(30) == []
    assert stats_by_signal_combo(30) == []


def test_stats_min_n_filter(tmp_path, monkeypatch):
    _setup_db_with_data(tmp_path, monkeypatch)
    from lib.knowledge_watcher.feedback_stats import stats_by_signal_combo
    # min_n=10 → all combos filtered out (none has 10)
    rows = stats_by_signal_combo(days=30, min_n=10)
    assert rows == []
