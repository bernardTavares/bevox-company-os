"""Tests for W8.P3.T3.2 — F1/F4 commands record decisions in feedback.db."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lib.knowledge_watcher.feedback_db import init_db
from lib.knowledge_watcher.gap_registry import (
    GapRecord, GapSource, GapStatus, add_gap,
)
from lib.knowledge_watcher import commands


@pytest.fixture
def fb_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    return db


def _state_with_gap(gap_id: str, source: GapSource, doc_type: str = "adr",
                    status: GapStatus = GapStatus.OPEN) -> dict:
    state = {"version": 2, "repos": {}, "global": {}}
    add_gap(state, GapRecord(
        gap_id=gap_id, repo="p1", source=source, status=status,
        doc_type=doc_type, commit_sha=None, path=f"30_adr/p1/{gap_id}.md",
        draft_branch=None, created_at=datetime.now(timezone.utc),
        snooze_until=None,
    ))
    return state


def _decisions_for(db_path: Path, gap_id: str):
    return sqlite3.connect(str(db_path)).execute(
        "SELECT decision, doc_type, project_slug FROM decisions "
        "WHERE gap_id = ?",
        (gap_id,),
    ).fetchall()


def test_cmd_dismiss_records_decision(fb_db):
    state = _state_with_gap("g1", GapSource.F1)
    r = commands.cmd_dismiss(state, "g1")
    assert r.ok
    assert _decisions_for(fb_db, "g1") == [("dismiss", "adr", "p1")]


def test_cmd_keep_records_decision(fb_db):
    state = _state_with_gap("g1", GapSource.F4)
    r = commands.cmd_keep(state, "g1")
    assert r.ok
    assert _decisions_for(fb_db, "g1") == [("keep", "adr", "p1")]


def test_cmd_postpone_records_decision(fb_db):
    state = _state_with_gap("g1", GapSource.F1)
    r = commands.cmd_postpone(state, "g1", days=7)
    assert r.ok
    assert _decisions_for(fb_db, "g1") == [("postpone", "adr", "p1")]


def test_cmd_dismiss_idempotent_does_not_double_record(fb_db):
    state = _state_with_gap("g1", GapSource.F4)
    commands.cmd_dismiss(state, "g1")
    commands.cmd_dismiss(state, "g1")  # already-dismissed → noop reply
    rows = _decisions_for(fb_db, "g1")
    assert len(rows) == 1


def test_failed_command_does_not_record(fb_db):
    """Gap not found → no decision row."""
    state = {"version": 2, "repos": {}, "global": {}}
    r = commands.cmd_dismiss(state, "nonexistent")
    assert not r.ok
    assert _decisions_for(fb_db, "nonexistent") == []
