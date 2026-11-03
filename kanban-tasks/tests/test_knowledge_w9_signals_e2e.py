"""E2E test for W9.T1 — signals flow scan → state.json → feedback.db.

Closes openclaw issue #27.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lib.knowledge_watcher.feedback_db import init_db
from lib.knowledge_watcher.gap_registry import (
    GapRecord, GapSource, GapStatus, add_gap, get_gap,
)
from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)
from lib.knowledge_watcher import commands


@pytest.fixture
def fb_db(tmp_path: Path, monkeypatch) -> Path:
    db = tmp_path / "fb.db"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_FEEDBACK_DB", str(db))
    init_db(db).close()
    return db


def test_gaprecord_round_trip_preserves_signals(tmp_path):
    """GapRecord with signals_json round-trips through state.json correctly."""
    state = {"version": 2, "repos": {}, "global": {}}
    signals_payload = [
        {"category": "B_code_broken", "confidence": 0.85, "evidence": "x"},
        {"category": "E_orphan", "confidence": 0.4, "evidence": "y"},
    ]
    g = GapRecord(
        gap_id="g1", repo="p1", source=GapSource.F4,
        status=GapStatus.OPEN, doc_type="adr",
        commit_sha=None, path="30_adr/p1/x.md",
        draft_branch=None, created_at=datetime.now(timezone.utc),
        snooze_until=None,
        signals_json=json.dumps(signals_payload),
    )
    add_gap(state, g)
    retrieved = get_gap(state, "g1")
    assert retrieved is not None
    assert retrieved.signals_json is not None
    parsed = json.loads(retrieved.signals_json)
    assert len(parsed) == 2
    assert {p["category"] for p in parsed} == {"B_code_broken", "E_orphan"}


def test_gaprecord_legacy_v2_state_has_no_signals(tmp_path):
    """GapRecord deserialized from v2 state.json (no signals_json key) → None."""
    state = {"version": 2, "repos": {"p1": {
        "gaps": {
            "g1": {
                "gap_id": "g1", "repo": "p1", "source": "f4",
                "status": "open", "doc_type": "adr",
                "commit_sha": None, "path": "30_adr/p1/x.md",
                "draft_branch": None,
                "created_at": "2026-05-09T10:00:00Z",
                "snooze_until": None,
                # NOTE: no signals_json key (legacy pre-W9 row)
            }
        }
    }}}
    g = get_gap(state, "g1")
    assert g is not None
    assert g.signals_json is None


def test_cmd_keep_records_real_signals(fb_db):
    """End-to-end: gap with signals_json → /keep → feedback.db has real combo."""
    state = {"version": 2, "repos": {}, "global": {}}
    signals_payload = [
        {"category": "B_code_broken", "confidence": 0.85, "evidence": "x"},
        {"category": "E_orphan", "confidence": 0.4, "evidence": "y"},
    ]
    g = GapRecord(
        gap_id="g1", repo="p1", source=GapSource.F4,
        status=GapStatus.OPEN, doc_type="adr",
        commit_sha=None, path="30_adr/p1/x.md",
        draft_branch=None, created_at=datetime.now(timezone.utc),
        snooze_until=None,
        signals_json=json.dumps(signals_payload),
    )
    add_gap(state, g)

    r = commands.cmd_keep(state, "g1")
    assert r.ok

    raw = sqlite3.connect(str(fb_db)).execute(
        "SELECT signals_json FROM decisions WHERE gap_id = 'g1'",
    ).fetchone()[0]
    parsed = json.loads(raw)
    cats = sorted({p["category"] for p in parsed})
    assert cats == ["B_code_broken", "E_orphan"]


def test_stats_by_signal_combo_returns_real_combo(fb_db):
    """After multiple /keep with signals, stats_by_signal_combo shows real combo."""
    state = {"version": 2, "repos": {}, "global": {}}
    for i in range(4):
        g = GapRecord(
            gap_id=f"g{i}", repo="p1", source=GapSource.F4,
            status=GapStatus.OPEN, doc_type="adr",
            commit_sha=None, path=f"30_adr/p1/x{i}.md",
            draft_branch=None, created_at=datetime.now(timezone.utc),
            snooze_until=None,
            signals_json=json.dumps([
                {"category": "B_code_broken", "confidence": 0.85, "evidence": "x"},
            ]),
        )
        add_gap(state, g)
        commands.cmd_keep(state, f"g{i}")

    from lib.knowledge_watcher.feedback_stats import stats_by_signal_combo
    rows = stats_by_signal_combo(days=30, min_n=1)
    combos = {(r["doc_type"], r["signal_combo"]) for r in rows}
    assert ("adr", "B") in combos  # not "none"!


def test_f1_gap_with_no_signals_still_records_as_none(fb_db):
    """F1 gaps (no categorial signals) still record decision with combo='none'."""
    state = {"version": 2, "repos": {}, "global": {}}
    g = GapRecord(
        gap_id="g_f1", repo="p1", source=GapSource.F1,
        status=GapStatus.OPEN, doc_type="spec",
        commit_sha="abc123", path="35_specs/p1/draft.md",
        draft_branch=None, created_at=datetime.now(timezone.utc),
        snooze_until=None,
        signals_json=None,  # F1 default
    )
    add_gap(state, g)
    r = commands.cmd_dismiss(state, "g_f1")
    assert r.ok

    raw = sqlite3.connect(str(fb_db)).execute(
        "SELECT signals_json FROM decisions WHERE gap_id = 'g_f1'",
    ).fetchone()[0]
    assert raw == "[]"  # empty list → combo "none" downstream


def test_add_gap_backfills_signals_for_legacy_row(tmp_path):
    """Legacy v2 row (signals_json=None) gets backfilled on re-scan."""
    # Pre-existing legacy gap
    state = {"version": 2, "repos": {"p1": {
        "gaps": {
            "g1": {
                "gap_id": "g1", "repo": "p1", "source": "f4",
                "status": "open", "doc_type": "adr",
                "commit_sha": None, "path": "30_adr/p1/x.md",
                "draft_branch": None,
                "created_at": "2026-05-09T10:00:00Z",
                "snooze_until": None,
            }
        }
    }}}
    # Re-scan produces new record with signals
    new = GapRecord(
        gap_id="g1", repo="p1", source=GapSource.F4,
        status=GapStatus.OPEN, doc_type="adr",
        commit_sha=None, path="30_adr/p1/x.md",
        draft_branch=None, created_at=datetime.now(timezone.utc),
        snooze_until=None,
        signals_json=json.dumps([{"category": "B_code_broken"}]),
    )
    add_gap(state, new)
    # Existing row's signals_json was backfilled (but status preserved)
    assert state["repos"]["p1"]["gaps"]["g1"]["signals_json"] is not None
    parsed = json.loads(state["repos"]["p1"]["gaps"]["g1"]["signals_json"])
    assert parsed[0]["category"] == "B_code_broken"
    assert state["repos"]["p1"]["gaps"]["g1"]["status"] == "open"  # preserved


def test_add_gap_idempotent_does_not_overwrite_existing_signals(tmp_path):
    """If existing row already has signals_json, no change."""
    existing_signals = json.dumps([{"category": "A_markers"}])
    state = {"version": 2, "repos": {"p1": {
        "gaps": {
            "g1": {
                "gap_id": "g1", "repo": "p1", "source": "f4",
                "status": "open", "doc_type": "adr",
                "commit_sha": None, "path": "30_adr/p1/x.md",
                "draft_branch": None,
                "created_at": "2026-05-09T10:00:00Z",
                "snooze_until": None,
                "signals_json": existing_signals,
            }
        }
    }}}
    new = GapRecord(
        gap_id="g1", repo="p1", source=GapSource.F4,
        status=GapStatus.OPEN, doc_type="adr",
        commit_sha=None, path="30_adr/p1/x.md",
        draft_branch=None, created_at=datetime.now(timezone.utc),
        snooze_until=None,
        signals_json=json.dumps([{"category": "B_code_broken"}]),
    )
    add_gap(state, new)
    # Original signals preserved
    assert state["repos"]["p1"]["gaps"]["g1"]["signals_json"] == existing_signals


def test_f4_scanner_persists_signals(tmp_path):
    """F4 scanner integration: writes signals_json into state when adding gaps."""
    kb = tmp_path / "kb"
    code = tmp_path / "code"
    (kb / "30_adr" / "p1").mkdir(parents=True)
    (kb / "30_adr" / "p1" / "ADR-001.md").write_text(
        "# ADR-001\n\n"
        "**Status:** Aceita\n\n"
        "## Context\n\n"
        "Refs `missing-file.ts` and `another-missing.ts`.\n"
    )
    (code / "p1").mkdir(parents=True)
    # Empty code dir → all refs are broken → B_code_broken signal triggers

    state = {"version": 2, "repos": {}, "global": {}}
    from lib.knowledge_watcher.retirement.scanner import scan_retirement_candidates
    scan_retirement_candidates(kb, code, project="p1", state=state)

    # Inspect state.json gaps
    gaps = state["repos"].get("p1", {}).get("gaps", {})
    for gid, d in gaps.items():
        assert d.get("signals_json") is not None
        parsed = json.loads(d["signals_json"])
        assert isinstance(parsed, list)
        assert len(parsed) >= 1
        # Should at least include B_code_broken (broken refs)
        cats = {p["category"] for p in parsed}
        assert "B_code_broken" in cats
