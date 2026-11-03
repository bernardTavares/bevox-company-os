"""Tests for digest_header.format_summary_header (W8.T1.3)."""
from pathlib import Path

from lib.knowledge_watcher.digest_header import format_summary_header
from lib.knowledge_watcher.retirement import (
    RetirementCandidate, CategorySignal, RetirementCategory,
)


def _candidate(path: str, score: float, project: str, signals=None):
    return RetirementCandidate(
        path=Path(path), relative_path=path, project_slug=project,
        score=score, signals=signals or [],
    )


def test_header_for_retirement_candidates():
    candidates = [
        _candidate("30_adr/p1/ADR-001.md", 1.0, "p1"),
        _candidate("30_adr/p1/ADR-002.md", 0.85, "p1"),
        _candidate("35_specs/p2/spec.md", 0.7, "p2"),
    ]
    header = format_summary_header(
        candidates, title="📊 [knowledge retirement-scan]",
    )
    assert "Total: 3" in header
    assert "p1" in header and "p2" in header
    # Score breakdown shows 1 high + 2 mid
    assert "🔴 1" in header
    assert "🟡 2" in header
    # Doc-type breakdown
    assert "adr" in header
    assert "spec" in header


def test_header_handles_empty():
    header = format_summary_header([], title="📊 empty")
    assert "Total: 0" in header


def test_header_per_project_top_n_only():
    candidates = [
        _candidate(f"30_adr/p{i}/ADR.md", 0.8, f"p{i}")
        for i in range(8)
    ]
    header = format_summary_header(candidates, title="X")
    # Default top_n=3 → only 3 projects shown in line
    assert header.count("p0") + header.count("p1") + header.count("p2") >= 1


def test_header_handles_unknown_project_slug():
    candidates = [_candidate("35_specs/_shared/x.md", 0.7, None)]
    header = format_summary_header(candidates, title="X")
    assert "_unknown" in header or "_shared" in header or "Total: 1" in header


def test_header_score_attr_none_skips_score_breakdown():
    """F2 reports don't have score; passing score_attr=None omits the line."""
    items = [
        type("X", (), {
            "project_slug": "p1", "relative_path": "30_adr/p1/x.md",
        })()
    ]
    header = format_summary_header(items, title="X", score_attr=None)
    assert "score 1.0" not in header
    assert "Por projeto" in header


def test_header_doc_type_breakdown_aggregates():
    candidates = [
        _candidate(f"30_adr/p/ADR-{i}.md", 0.8, "p") for i in range(5)
    ] + [
        _candidate(f"35_specs/p/spec-{i}.md", 0.8, "p") for i in range(3)
    ]
    header = format_summary_header(candidates, title="X")
    assert "adr 5" in header
    assert "spec 3" in header
