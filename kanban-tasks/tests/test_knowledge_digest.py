"""Tests for lib/knowledge_watcher/digest.py — delta detection + idempotência."""
from lib.knowledge_watcher.digest import (
    compute_gap_signature,
    detect_new_gaps,
    update_state_with_gaps,
)
from lib.knowledge_watcher.gap_report import ProjectGapReport, FolderGap
from lib.knowledge_watcher.expectations import Severity


def test_compute_gap_signature_stable():
    """Same gaps produce same signature (deterministic)."""
    gaps = [
        FolderGap("10_prd", Severity.ALWAYS_REQUIRED, 0, "x"),
        FolderGap("40_roadmap", Severity.ALWAYS_REQUIRED, 0, "y"),
    ]
    sig1 = compute_gap_signature("alpha", gaps)
    sig2 = compute_gap_signature("alpha", gaps)
    assert sig1 == sig2


def test_compute_gap_signature_different_for_different_gaps():
    """Different gaps produce different signatures."""
    g1 = [FolderGap("10_prd", Severity.ALWAYS_REQUIRED, 0, "x")]
    g2 = [FolderGap("40_roadmap", Severity.ALWAYS_REQUIRED, 0, "x")]
    assert compute_gap_signature("alpha", g1) != compute_gap_signature("alpha", g2)


def test_detect_new_gaps_first_run():
    """First run with no prior state → all gaps are "new"."""
    reports = [
        ProjectGapReport(
            slug="alpha",
            gaps=[FolderGap("10_prd", Severity.ALWAYS_REQUIRED, 0, "x")],
        ),
    ]
    state = {"version": 1, "repos": {}, "global": {}}
    new = detect_new_gaps(reports, state)
    assert len(new) == 1
    assert new[0].slug == "alpha"


def test_detect_new_gaps_no_change():
    """If signatures match prior state → empty (idempotent)."""
    reports = [
        ProjectGapReport(
            slug="alpha",
            gaps=[FolderGap("10_prd", Severity.ALWAYS_REQUIRED, 0, "x")],
        ),
    ]
    sig = compute_gap_signature("alpha", reports[0].gaps)
    state = {"version": 1, "repos": {"alpha": {"last_gap_signature": sig}}, "global": {}}
    new = detect_new_gaps(reports, state)
    assert new == []


def test_detect_new_gaps_change_detected():
    """Signature mismatch → reported as new."""
    reports = [
        ProjectGapReport(
            slug="alpha",
            gaps=[FolderGap("10_prd", Severity.ALWAYS_REQUIRED, 0, "x")],
        ),
    ]
    state = {"version": 1, "repos": {"alpha": {"last_gap_signature": "old_sig"}}, "global": {}}
    new = detect_new_gaps(reports, state)
    assert len(new) == 1


def test_update_state_with_gaps_persists_signatures():
    """update_state_with_gaps writes signature + gaps_open count."""
    reports = [
        ProjectGapReport(
            slug="alpha",
            gaps=[
                FolderGap("10_prd", Severity.ALWAYS_REQUIRED, 0, "x"),
                FolderGap("30_adr", Severity.CONDITIONAL, 0, "y"),
            ],
        ),
    ]
    state = {"version": 1, "repos": {}, "global": {}}
    updated = update_state_with_gaps(state, reports)
    assert "alpha" in updated["repos"]
    assert updated["repos"]["alpha"]["gaps_open"] == 2
    assert "last_gap_signature" in updated["repos"]["alpha"]
    expected_sig = compute_gap_signature("alpha", reports[0].gaps)
    assert updated["repos"]["alpha"]["last_gap_signature"] == expected_sig
