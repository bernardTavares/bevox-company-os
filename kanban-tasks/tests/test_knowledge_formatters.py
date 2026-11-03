"""Tests for lib/knowledge_watcher/formatters.py."""
import json
from pathlib import Path

from lib.knowledge_watcher.gap_report import ProjectGapReport, FolderGap
from lib.knowledge_watcher.expectations import Severity
from lib.knowledge_watcher.formatters import (
    format_human, format_json,
    format_retirement_human, format_retirement_json,
)
from lib.knowledge_watcher.retirement import (
    RetirementCandidate, CategorySignal, RetirementCategory,
)


def _sample_report():
    return [
        ProjectGapReport(
            slug="alpha",
            context={"age_months": 8, "commit_count": 150},
            gaps=[
                FolderGap("10_prd", Severity.ALWAYS_REQUIRED, 0, "always-required"),
                FolderGap("30_adr", Severity.CONDITIONAL, 0, "established (8mo, 150 commits)"),
            ],
        ),
        ProjectGapReport(
            slug="beta",
            context={"age_months": 1, "commit_count": 10},
            gaps=[],
        ),
    ]


def test_format_human_includes_slug_and_severity_markers():
    output = format_human(_sample_report())
    assert "alpha" in output
    assert "beta" in output
    assert "❌" in output or "MISSING" in output  # always-required marker
    assert "⚠️" in output or "GAP" in output  # conditional marker


def test_format_human_includes_clean_projects_in_summary():
    """Beta has 0 gaps — should appear as clean."""
    output = format_human(_sample_report())
    assert "beta" in output


def test_format_json_round_trip():
    output = format_json(_sample_report())
    parsed = json.loads(output)
    assert isinstance(parsed, list)
    assert parsed[0]["slug"] == "alpha"
    assert len(parsed[0]["gaps"]) == 2
    assert parsed[0]["gaps"][0]["severity"] == "always-required"
    assert parsed[0]["gaps"][0]["folder"] == "10_prd"


def test_format_human_empty_list():
    output = format_human([])
    assert "no opted-in projects" in output.lower() or "nothing" in output.lower()


def test_format_json_empty_list():
    output = format_json([])
    parsed = json.loads(output)
    assert parsed == []


# --- F4 retirement formatters ---


def _sample_candidates():
    return [
        RetirementCandidate(
            path=Path("/kb/30_adr/bevox-direct/ADR-005.md"),
            relative_path="30_adr/bevox-direct/ADR-005.md",
            project_slug="bevox-direct",
            score=0.85,
            signals=[
                CategorySignal(
                    category=RetirementCategory.A_MARKERS,
                    confidence=1.00,
                    evidence='"Status: Superseded" found in front-matter',
                ),
                CategorySignal(
                    category=RetirementCategory.C_SUPERSESSION,
                    confidence=0.70,
                    evidence="newer doc 2026-04-12-foo.md supersedes 2025-08-01-foo.md",
                ),
            ],
        ),
        RetirementCandidate(
            path=Path("/kb/35_specs/openclaw/old-spec.md"),
            relative_path="35_specs/openclaw/old-spec.md",
            project_slug="openclaw",
            score=0.72,
            signals=[
                CategorySignal(
                    category=RetirementCategory.D_LIFECYCLE,
                    confidence=0.72,
                    evidence="status: done + age > 6 months",
                ),
            ],
        ),
    ]


def test_format_retirement_human_empty_list():
    output = format_retirement_human([])
    assert "no retirement candidates" in output.lower()
    assert "[retirement scan]" in output.lower()


def test_format_retirement_human_with_candidates():
    output = format_retirement_human(_sample_candidates())
    assert "2 retirement candidate" in output
    assert "30_adr/bevox-direct/ADR-005.md" in output
    assert "0.85" in output
    assert "bevox-direct" in output
    assert "A_markers" in output
    assert "1.00" in output
    assert "Superseded" in output
    assert "C_supersession" in output
    assert "0.70" in output
    assert "35_specs/openclaw/old-spec.md" in output
    assert "D_lifecycle" in output
    assert "Review humano obrigatório" in output
    # W3.5: commands use gap_id
    from lib.knowledge_watcher.gap_registry import derive_gap_id_f4
    for c in _sample_candidates():
        if c.project_slug:
            gid = derive_gap_id_f4(c.project_slug, c.relative_path)
            assert f"/retire {gid}" in output
            assert f"/keep {gid}" in output
            assert f"/keep-permanent {gid}" in output


def test_format_retirement_human_includes_commands():
    """W3.5: format_retirement_human emits /retire /keep /keep-permanent per slugged candidate."""
    from lib.knowledge_watcher.gap_registry import derive_gap_id_f4
    c = RetirementCandidate(
        path=Path("/tmp/30_adr/bevox-direct/ADR-001.md"),
        relative_path="30_adr/bevox-direct/ADR-001.md",
        project_slug="bevox-direct",
        score=0.85,
        signals=[
            CategorySignal(
                category=RetirementCategory.A_MARKERS,
                confidence=1.0, evidence="Status: Superseded",
            )
        ],
    )
    out = format_retirement_human([c])
    expected_id = derive_gap_id_f4("bevox-direct", "30_adr/bevox-direct/ADR-001.md")
    assert expected_id in out
    assert f"/retire {expected_id}" in out
    assert f"/keep {expected_id}" in out
    assert f"/keep-permanent {expected_id}" in out


def test_format_retirement_human_skips_commands_for_shared():
    """_shared candidates não têm comandos (sem project_slug)."""
    c = RetirementCandidate(
        path=Path("/tmp/30_adr/_shared/ADR-X.md"),
        relative_path="30_adr/_shared/ADR-X.md",
        project_slug=None,
        score=0.85,
        signals=[
            CategorySignal(
                category=RetirementCategory.A_MARKERS,
                confidence=1.0, evidence="Status: Superseded",
            )
        ],
    )
    out = format_retirement_human([c])
    # No /retire, /keep, /keep-permanent — render só com warning visual
    assert "/retire" not in out
    assert "/keep " not in out
    assert "_shared — sem comandos diretos" in out


def test_format_retirement_json_empty_list():
    output = format_retirement_json([])
    parsed = json.loads(output)
    assert parsed == []


def test_format_retirement_json_round_trip():
    output = format_retirement_json(_sample_candidates())
    parsed = json.loads(output)
    assert isinstance(parsed, list)
    assert len(parsed) == 2

    first = parsed[0]
    assert first["path"] == "30_adr/bevox-direct/ADR-005.md"
    assert first["project_slug"] == "bevox-direct"
    assert first["score"] == 0.85
    assert len(first["signals"]) == 2
    assert first["signals"][0]["category"] == "A_markers"
    assert first["signals"][0]["confidence"] == 1.00
    assert "Superseded" in first["signals"][0]["evidence"]
    assert first["signals"][1]["category"] == "C_supersession"

    second = parsed[1]
    assert second["project_slug"] == "openclaw"
    assert second["signals"][0]["category"] == "D_lifecycle"
