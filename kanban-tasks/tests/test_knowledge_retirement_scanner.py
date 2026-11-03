"""Tests for retirement/scanner.py — integration."""
from pathlib import Path

import pytest

from lib.knowledge_watcher.retirement.scanner import (
    scan_retirement_candidates, _extract_slug, _doc_type_from_path,
)
from lib.knowledge_watcher.folder_audit import CANONICAL_FOLDERS


def _make_kb(tmp_path):
    kb = tmp_path / "knowledge"
    for folder in CANONICAL_FOLDERS:
        (kb / folder).mkdir(parents=True)
    return kb


def test_extract_slug_from_canonical_path(tmp_path):
    kb = tmp_path / "kb"
    doc = kb / "30_adr" / "bevox-direct" / "ADR-001.md"
    assert _extract_slug(doc, kb) == "bevox-direct"


def test_extract_slug_shared_returns_none(tmp_path):
    kb = tmp_path / "kb"
    doc = kb / "30_adr" / "_shared" / "ADR-013.md"
    assert _extract_slug(doc, kb) is None


def test_empty_kb_returns_empty(tmp_path):
    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    candidates = scan_retirement_candidates(kb, code)
    assert candidates == []


def test_doc_with_status_superseded_flagged(tmp_path):
    """ADR with `Status: Superseded by X` → Cat A → score 1.0 → flagged."""
    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    adr = kb / "30_adr" / "bevox-direct" / "ADR-001.md"
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text("---\nstatus: Superseded by ADR-005\n---\n# ADR-001")

    candidates = scan_retirement_candidates(kb, code)
    assert len(candidates) == 1
    assert candidates[0].score >= 0.7
    assert candidates[0].project_slug == "bevox-direct"
    assert "ADR-001" in candidates[0].relative_path


def test_active_doc_not_flagged(tmp_path):
    """Status: Aceita → no signals → not flagged."""
    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    adr = kb / "30_adr" / "bevox-direct" / "ADR-001.md"
    adr.parent.mkdir(parents=True, exist_ok=True)
    adr.write_text("---\nstatus: Aceita\n---\n# ADR-001\n\nLook at `apps/api/main.ts`.")
    # Create the referenced file so Cat B doesn't fire
    (code / "bevox-direct" / "apps" / "api").mkdir(parents=True)
    (code / "bevox-direct" / "apps" / "api" / "main.ts").write_text("// real")

    candidates = scan_retirement_candidates(kb, code)
    # Could have orphan signal (Cat E, 0.3) but alone < threshold
    flagged = [c for c in candidates if c.score >= 0.7]
    assert flagged == []


def test_retired_dir_excluded(tmp_path):
    """Docs in _retired/ are not candidates."""
    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    retired = kb / "_retired" / "old"
    retired.mkdir(parents=True)
    (retired / "old.md").write_text("---\nstatus: Superseded by X\n---\n# old")

    candidates = scan_retirement_candidates(kb, code)
    assert candidates == []


def test_filter_by_project(tmp_path):
    """--project filter limits scan."""
    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    # Two projects, both with retirement candidates
    for slug in ("alpha", "beta"):
        adr = kb / "30_adr" / slug / "ADR-001.md"
        adr.parent.mkdir(parents=True, exist_ok=True)
        adr.write_text("---\nstatus: Superseded by X\n---\n# ADR-001")

    candidates = scan_retirement_candidates(kb, code, project="alpha")
    assert all(c.project_slug == "alpha" for c in candidates)
    assert len(candidates) == 1


def test_kb_missing_returns_empty(tmp_path):
    fake_kb = tmp_path / "no-kb"
    code = tmp_path / "code"
    code.mkdir()
    assert scan_retirement_candidates(fake_kb, code) == []


# ---------------------------------------------------------------------------
# W3.5: _doc_type_from_path helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rel_path,expected", [
    ("30_adr/bevox-direct/ADR-001.md", "adr"),
    ("10_prd/bevox-direct/PRD-001.md", "prd"),
    ("20_architecture/bevox-direct/system-map.md", "architecture"),
    ("35_specs/bevox-direct/spec.md", "spec"),
    ("40_roadmap/bevox-direct/roadmap.md", "roadmap"),
    ("50_releases/bevox-direct/release.md", "release-note"),
    ("60_customer-feedback/bevox-direct/fb.md", "customer-feedback"),
    ("70_metrics/bevox-direct/metrics.md", "metrics"),
    ("00_inbox/bevox-direct/note.md", "inbox"),
    ("unknown/bevox-direct/doc.md", "unknown"),
])
def test_doc_type_from_path(rel_path, expected):
    assert _doc_type_from_path(rel_path) == expected


# ---------------------------------------------------------------------------
# W3.5: state registration
# ---------------------------------------------------------------------------

def test_scanner_registers_f4_gaps_in_state(tmp_path):
    """W3.5: scan_retirement_candidates registers each candidate in state."""
    from lib.knowledge_watcher.gap_registry import (
        get_gap, derive_gap_id_f4, GapStatus, GapSource,
    )
    from lib.knowledge_watcher.state import default_state

    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    # ADR with explicit "Status: Superseded" marker (Cat A → score 1.0 → flagged)
    adr_dir = kb / "30_adr" / "bevox-direct"
    adr_dir.mkdir(parents=True, exist_ok=True)
    adr = adr_dir / "ADR-001-old.md"
    adr.write_text("---\nstatus: Superseded by ADR-005\n---\n# ADR-001\n\nbody.\n")

    state = default_state()
    candidates = scan_retirement_candidates(kb, code, state=state)

    flagged = [c for c in candidates if c.project_slug == "bevox-direct"]
    assert len(flagged) >= 1, "fixture must produce at least 1 flagged candidate"

    c = flagged[0]
    expected_id = derive_gap_id_f4(c.project_slug, c.relative_path)
    g = get_gap(state, expected_id)

    assert g is not None, f"gap {expected_id} not found in state"
    assert g.source is GapSource.F4
    assert g.status is GapStatus.OPEN
    assert g.repo == "bevox-direct"
    assert g.path == c.relative_path
    assert g.doc_type == "adr"


def test_scanner_registers_gap_idempotent(tmp_path):
    """Calling scan twice with same state does not duplicate the gap."""
    from lib.knowledge_watcher.gap_registry import list_open_gaps
    from lib.knowledge_watcher.state import default_state

    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    adr_dir = kb / "30_adr" / "bevox-direct"
    adr_dir.mkdir(parents=True, exist_ok=True)
    (adr_dir / "ADR-001.md").write_text(
        "---\nstatus: Superseded by ADR-005\n---\n# ADR-001\n"
    )

    state = default_state()
    scan_retirement_candidates(kb, code, state=state)
    gaps_after_first = list(list_open_gaps(state, repo="bevox-direct"))

    scan_retirement_candidates(kb, code, state=state)
    gaps_after_second = list(list_open_gaps(state, repo="bevox-direct"))

    assert len(gaps_after_first) == len(gaps_after_second)


def test_scanner_skips_shared_docs(tmp_path):
    """_shared docs (project_slug=None) are NOT registered in state."""
    from lib.knowledge_watcher.state import default_state

    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    shared_dir = kb / "30_adr" / "_shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    (shared_dir / "ADR-X.md").write_text(
        "---\nstatus: Superseded\n---\n# ADR-X\n\nbody.\n"
    )

    state = default_state()
    scan_retirement_candidates(kb, code, state=state)

    total_gaps = sum(
        len(rs.get("gaps", {})) for rs in state.get("repos", {}).values()
    )
    assert total_gaps == 0, "no gaps should be registered for _shared docs"


def test_scanner_no_state_backward_compat(tmp_path):
    """Calling without state= still works and returns candidates normally."""
    kb = _make_kb(tmp_path)
    code = tmp_path / "code"
    code.mkdir()
    adr_dir = kb / "30_adr" / "bevox-direct"
    adr_dir.mkdir(parents=True, exist_ok=True)
    (adr_dir / "ADR-001.md").write_text(
        "---\nstatus: Superseded by ADR-005\n---\n# ADR-001\n"
    )

    # state not passed — must not raise
    candidates = scan_retirement_candidates(kb, code)
    assert len(candidates) >= 1
