"""Tests for feedback.py — capture helpers (W8.P3.T3.1)."""
import json
import sqlite3
from pathlib import Path

from lib.knowledge_watcher.feedback_db import init_db
from lib.knowledge_watcher.feedback import (
    record_decision, record_f3_output_initial, record_f3_accept,
)
from lib.knowledge_watcher.retirement import CategorySignal, RetirementCategory


def _setup_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    return db


def test_record_decision_creates_row(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record_decision(
        gap_id="g1", source="f4", doc_type="adr", project_slug="p1",
        signals=[CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.8, "x")],
        decision="keep",
    )
    rows = sqlite3.connect(str(db)).execute(
        "SELECT gap_id, doc_type, decision, source, project_slug "
        "FROM decisions",
    ).fetchall()
    assert rows == [("g1", "adr", "keep", "f4", "p1")]


def test_record_decision_signals_serialized(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record_decision(
        gap_id="g1", source="f4", doc_type="spec", project_slug="p1",
        signals=[
            CategorySignal(RetirementCategory.A_MARKERS, 0.95, "deprecated"),
            CategorySignal(RetirementCategory.B_CODE_BROKEN, 0.7, "broken refs"),
        ],
        decision="retire",
    )
    raw = sqlite3.connect(str(db)).execute(
        "SELECT signals_json FROM decisions WHERE gap_id = 'g1'",
    ).fetchone()[0]
    parsed = json.loads(raw)
    assert len(parsed) == 2
    assert {p["category"] for p in parsed} == {"A_markers", "B_code_broken"}


def test_record_decision_idempotent_same_day(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record_decision(gap_id="g1", source="f4", doc_type="adr",
                    project_slug=None, signals=[], decision="keep")
    record_decision(gap_id="g1", source="f4", doc_type="adr",
                    project_slug=None, signals=[], decision="keep")
    n = sqlite3.connect(str(db)).execute(
        "SELECT COUNT(*) FROM decisions",
    ).fetchone()[0]
    assert n == 1


def test_record_decision_different_decision_same_gap_creates_two(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record_decision(gap_id="g1", source="f4", doc_type="adr",
                    project_slug=None, signals=[], decision="keep")
    record_decision(gap_id="g1", source="f4", doc_type="adr",
                    project_slug=None, signals=[], decision="retire")
    n = sqlite3.connect(str(db)).execute(
        "SELECT COUNT(*) FROM decisions",
    ).fetchone()[0]
    assert n == 2


def test_record_f3_output_initial_returns_id(tmp_path, monkeypatch):
    _setup_db(tmp_path, monkeypatch)
    rid = record_f3_output_initial(
        doc_path="30_adr/p/ADR-001.md", generator="adr",
        prompt_hash="abc123", content="initial draft", cost_usd=0.10,
    )
    assert rid > 0


def test_record_f3_accept_computes_edit_distance(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record_f3_output_initial(
        doc_path="30_adr/p/ADR-001.md", generator="adr",
        prompt_hash="abc", content="initial draft text", cost_usd=0.10,
    )
    record_f3_accept(
        doc_path="30_adr/p/ADR-001.md",
        content_accepted="initial draft text — heavily edited and expanded",
    )
    row = sqlite3.connect(str(db)).execute(
        "SELECT generator, edit_distance_ratio, cost_usd, accepted_at "
        "FROM f3_outputs",
    ).fetchone()
    assert row[0] == "adr"
    assert 0.0 < row[1] < 1.0
    assert row[2] == 0.10
    assert row[3] is not None  # accepted_at stamped


def test_record_f3_accept_no_op_if_no_initial(tmp_path, monkeypatch):
    """Accepting without prior generation row is silent no-op (legacy F3 docs)."""
    db = _setup_db(tmp_path, monkeypatch)
    record_f3_accept(
        doc_path="30_adr/p/ADR-001.md",
        content_accepted="something",
    )
    n = sqlite3.connect(str(db)).execute(
        "SELECT COUNT(*) FROM f3_outputs",
    ).fetchone()[0]
    assert n == 0


def test_record_f3_accept_zero_distance_for_identical(tmp_path, monkeypatch):
    db = _setup_db(tmp_path, monkeypatch)
    record_f3_output_initial(
        doc_path="30_adr/p/x.md", generator="adr",
        prompt_hash="x", content="exact same", cost_usd=0.0,
    )
    record_f3_accept(doc_path="30_adr/p/x.md", content_accepted="exact same")
    row = sqlite3.connect(str(db)).execute(
        "SELECT edit_distance_ratio FROM f3_outputs",
    ).fetchone()
    assert row[0] == 0.0
