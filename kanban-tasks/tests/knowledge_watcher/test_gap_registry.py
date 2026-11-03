"""Tests for gap_registry — GapRecord dataclass + helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from lib.knowledge_watcher.gap_registry import (
    GapRecord, GapStatus, GapSource,
)


def test_gap_record_required_fields():
    g = GapRecord(
        gap_id="bevox-direct-a1b2c3d-spec",
        repo="bevox-direct",
        source=GapSource.F1,
        status=GapStatus.OPEN,
        doc_type="spec",
        commit_sha="a1b2c3d4e5f6",
        path="00_inbox/bevox-direct/2026-05-09-feat-template-spec-draft.md",
        draft_branch="draft/auto/2026-05-09-a1b2c3d-spec",
        created_at=datetime(2026, 5, 9, 14, 30, tzinfo=timezone.utc),
        snooze_until=None,
    )
    assert g.gap_id == "bevox-direct-a1b2c3d-spec"
    assert g.source is GapSource.F1
    assert g.status is GapStatus.OPEN


def test_gap_status_terminal_set():
    assert GapStatus.OPEN.is_terminal is False
    assert GapStatus.SNOOZED.is_terminal is False
    assert GapStatus.DISMISSED.is_terminal is True
    assert GapStatus.ACCEPTED.is_terminal is True
    assert GapStatus.RETIRED.is_terminal is True


def test_derive_gap_id_f1_deterministic():
    from lib.knowledge_watcher.gap_registry import derive_gap_id_f1
    a = derive_gap_id_f1("bevox-direct", "a1b2c3d4e5f6", "spec")
    b = derive_gap_id_f1("bevox-direct", "a1b2c3d4e5f6", "spec")
    assert a == b == "bevox-direct-a1b2c3d-spec"


def test_derive_gap_id_f1_different_doctype():
    from lib.knowledge_watcher.gap_registry import derive_gap_id_f1
    a = derive_gap_id_f1("bevox-direct", "a1b2c3d4e5f6", "spec")
    b = derive_gap_id_f1("bevox-direct", "a1b2c3d4e5f6", "adr")
    assert a != b


def test_derive_gap_id_f4_deterministic():
    from lib.knowledge_watcher.gap_registry import derive_gap_id_f4
    a = derive_gap_id_f4("bevox-direct", "30_adr/bevox-direct/ADR-001-foo.md")
    b = derive_gap_id_f4("bevox-direct", "30_adr/bevox-direct/ADR-001-foo.md")
    assert a == b
    assert a.startswith("bevox-direct-r-") and len(a.split("-")[-1]) == 6


def test_derive_gap_id_f4_different_paths():
    from lib.knowledge_watcher.gap_registry import derive_gap_id_f4
    a = derive_gap_id_f4("bevox-direct", "30_adr/bevox-direct/ADR-001.md")
    b = derive_gap_id_f4("bevox-direct", "30_adr/bevox-direct/ADR-002.md")
    assert a != b


# Tests for helpers: add_gap, get_gap, update_gap, list_open_gaps
from lib.knowledge_watcher.state import default_state


def _make_gap(gap_id="bevox-direct-a1b2c3d-spec") -> GapRecord:
    return GapRecord(
        gap_id=gap_id, repo="bevox-direct", source=GapSource.F1,
        status=GapStatus.OPEN, doc_type="spec",
        commit_sha="a1b2c3d4e5f6",
        path="00_inbox/bevox-direct/2026-05-09-foo.md",
        draft_branch="draft/auto/2026-05-09-a1b2c3d-spec",
        created_at=datetime(2026, 5, 9, 14, 30, tzinfo=timezone.utc),
        snooze_until=None,
    )


def test_add_gap_writes_into_state():
    from lib.knowledge_watcher.gap_registry import add_gap
    state = default_state()
    g = _make_gap()
    add_gap(state, g)
    assert "bevox-direct" in state["repos"]
    assert g.gap_id in state["repos"]["bevox-direct"]["gaps"]


def test_add_gap_idempotent():
    from lib.knowledge_watcher.gap_registry import add_gap
    state = default_state()
    g = _make_gap()
    add_gap(state, g)
    add_gap(state, g)
    assert len(state["repos"]["bevox-direct"]["gaps"]) == 1


def test_get_gap_returns_record():
    from lib.knowledge_watcher.gap_registry import add_gap, get_gap
    state = default_state()
    g = _make_gap()
    add_gap(state, g)
    fetched = get_gap(state, g.gap_id)
    assert fetched is not None
    assert fetched.gap_id == g.gap_id
    assert fetched.status is GapStatus.OPEN


def test_get_gap_missing_returns_none():
    from lib.knowledge_watcher.gap_registry import get_gap
    state = default_state()
    assert get_gap(state, "nonexistent-id") is None


def test_update_gap_status():
    from lib.knowledge_watcher.gap_registry import add_gap, update_gap, get_gap
    state = default_state()
    g = _make_gap()
    add_gap(state, g)
    update_gap(state, g.gap_id, status=GapStatus.DISMISSED)
    fetched = get_gap(state, g.gap_id)
    assert fetched.status is GapStatus.DISMISSED


def test_list_open_gaps_filters_terminal():
    from lib.knowledge_watcher.gap_registry import add_gap, update_gap, list_open_gaps
    state = default_state()
    g1 = _make_gap("bevox-direct-aaa-spec")
    g2 = _make_gap("bevox-direct-bbb-spec")
    add_gap(state, g1)
    add_gap(state, g2)
    update_gap(state, g2.gap_id, status=GapStatus.DISMISSED)
    open_gaps = list_open_gaps(state, repo="bevox-direct")
    ids = [g.gap_id for g in open_gaps]
    assert g1.gap_id in ids
    assert g2.gap_id not in ids
