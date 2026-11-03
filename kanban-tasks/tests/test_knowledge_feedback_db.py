"""Tests for feedback_db.py — SQLite schema + init (W8.P2.T2.1)."""
import sqlite3
from pathlib import Path

from lib.knowledge_watcher.feedback_db import init_db, SCHEMA_VERSION


def test_init_db_creates_schema(tmp_path: Path):
    db_path = tmp_path / "feedback.db"
    conn = init_db(db_path)
    try:
        tables = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            ).fetchall()
        }
        assert "schema_version" in tables
        assert "decisions" in tables
        assert "f3_outputs" in tables

        # version stamped
        v = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        assert v == SCHEMA_VERSION
    finally:
        conn.close()


def test_init_db_idempotent_no_duplicate_version_rows(tmp_path: Path):
    db_path = tmp_path / "feedback.db"
    init_db(db_path).close()
    init_db(db_path).close()  # second call no-op
    conn = sqlite3.connect(str(db_path))
    n = conn.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    conn.close()
    assert n == 1


def test_init_db_enables_wal(tmp_path: Path):
    db_path = tmp_path / "feedback.db"
    conn = init_db(db_path)
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
    finally:
        conn.close()


def test_init_db_creates_parent_dir(tmp_path: Path):
    nested = tmp_path / "a" / "b" / "c" / "feedback.db"
    init_db(nested).close()
    assert nested.exists()


def test_init_db_indexes_present(tmp_path: Path):
    db_path = tmp_path / "feedback.db"
    conn = init_db(db_path)
    try:
        idx_names = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'",
            ).fetchall()
        }
        # Indexes from schema
        assert "idx_decisions_ts" in idx_names
        assert "idx_decisions_doctype" in idx_names
        assert "idx_decisions_decision" in idx_names
        assert "idx_f3_generator" in idx_names
        assert "idx_f3_accepted_at" in idx_names
    finally:
        conn.close()


def test_decisions_table_has_unique_constraint(tmp_path: Path):
    """(gap_id, decision, day) is unique — re-record same-day no-op."""
    db_path = tmp_path / "feedback.db"
    conn = init_db(db_path)
    try:
        # First insert OK
        conn.execute(
            "INSERT INTO decisions (ts, gap_id, source, decision) "
            "VALUES (?, ?, ?, ?)",
            ("2026-05-10T10:00:00Z", "g1", "f4", "keep"),
        )
        # Second insert same day → IGNORE (no error, but no duplicate row)
        conn.execute(
            "INSERT OR IGNORE INTO decisions (ts, gap_id, source, decision) "
            "VALUES (?, ?, ?, ?)",
            ("2026-05-10T11:00:00Z", "g1", "f4", "keep"),
        )
        n = conn.execute(
            "SELECT COUNT(*) FROM decisions WHERE gap_id = 'g1'",
        ).fetchone()[0]
        assert n == 1
    finally:
        conn.close()
