"""Tests for lib/knowledge_watcher/gap_report.py — orchestrator (integration)."""
import json
import subprocess
from pathlib import Path

import pytest

from lib.knowledge_watcher.gap_report import (
    run_gap_report,
    ProjectGapReport,
    FolderGap,
)
from lib.knowledge_watcher.expectations import Severity
from lib.knowledge_watcher.folder_audit import CANONICAL_FOLDERS


@pytest.fixture
def tmp_kb(tmp_path):
    """Build temp bevox-knowledge structure with all 9 canonical folders."""
    kb = tmp_path / "knowledge"
    for folder in CANONICAL_FOLDERS:
        (kb / folder).mkdir(parents=True)
    return kb


@pytest.fixture
def tmp_code_root(tmp_path):
    """Code root with simple repo per slug."""
    code = tmp_path / "code"
    code.mkdir()
    return code


def _make_repo(code_root: Path, slug: str):
    """Create empty git repo for slug."""
    repo = code_root / slug
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "x@x"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "x"], cwd=repo, check=True)
    (repo / "README.md").write_text("hi")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    return repo


def _meta_with_projects(*slugs):
    return {
        "version": 1,
        "projects": {
            slug: {"name": slug, "source": "adopted"} for slug in slugs
        },
    }


def test_no_projects_returns_empty(tmp_kb, tmp_code_root):
    """Empty meta → empty result."""
    meta = {"version": 1, "projects": {}}
    result = run_gap_report(tmp_kb, tmp_code_root, meta)
    assert result == []


def test_project_with_all_required_filled_returns_no_gaps(tmp_kb, tmp_code_root):
    """Project with PRD + roadmap (always-required) → no MISSING gaps."""
    _make_repo(tmp_code_root, "alpha")
    (tmp_kb / "10_prd" / "alpha").mkdir(parents=True)
    (tmp_kb / "10_prd" / "alpha" / "prd.md").write_text("# prd")
    (tmp_kb / "40_roadmap" / "alpha").mkdir(parents=True)
    (tmp_kb / "40_roadmap" / "alpha" / "roadmap.md").write_text("# rm")
    meta = _meta_with_projects("alpha")

    result = run_gap_report(tmp_kb, tmp_code_root, meta)
    assert len(result) == 1
    report = result[0]
    assert report.slug == "alpha"
    missing = [g for g in report.gaps if g.severity == Severity.ALWAYS_REQUIRED]
    assert missing == []


def test_project_missing_prd_reports_always_required_gap(tmp_kb, tmp_code_root):
    """Adopted project with no PRD → ALWAYS_REQUIRED gap on 10_prd."""
    _make_repo(tmp_code_root, "alpha")
    (tmp_kb / "40_roadmap" / "alpha").mkdir(parents=True)
    (tmp_kb / "40_roadmap" / "alpha" / "roadmap.md").write_text("# rm")
    meta = _meta_with_projects("alpha")

    result = run_gap_report(tmp_kb, tmp_code_root, meta)
    report = result[0]
    prd_gaps = [g for g in report.gaps if g.folder == "10_prd"]
    assert len(prd_gaps) == 1
    assert prd_gaps[0].severity == Severity.ALWAYS_REQUIRED
    assert prd_gaps[0].canonical_count == 0


def test_opt_out_project_skipped(tmp_kb, tmp_code_root):
    """Project with knowledge_watcher.opt_in=false is excluded."""
    _make_repo(tmp_code_root, "alpha")
    meta = {
        "version": 1,
        "projects": {
            "alpha": {
                "name": "alpha", "source": "adopted",
                "knowledge_watcher": {"opt_in": False},
            },
        },
    }
    result = run_gap_report(tmp_kb, tmp_code_root, meta)
    assert result == []


def test_legacy_project_without_knowledge_watcher_field_included(tmp_kb, tmp_code_root):
    """Backward-compat: missing knowledge_watcher field → opt-in default."""
    _make_repo(tmp_code_root, "alpha")
    meta = {
        "version": 1,
        "projects": {
            "alpha": {"name": "alpha", "source": "adopted"},  # no knowledge_watcher
        },
    }
    result = run_gap_report(tmp_kb, tmp_code_root, meta)
    assert len(result) == 1


def test_filter_by_project(tmp_kb, tmp_code_root):
    """Filter --project beta returns only beta's report."""
    _make_repo(tmp_code_root, "alpha")
    _make_repo(tmp_code_root, "beta")
    meta = _meta_with_projects("alpha", "beta")

    result = run_gap_report(tmp_kb, tmp_code_root, meta, project="beta")
    assert len(result) == 1
    assert result[0].slug == "beta"


def test_filter_by_severity_always_required(tmp_kb, tmp_code_root):
    """--severity always-required filters to those gaps only."""
    _make_repo(tmp_code_root, "alpha")
    meta = _meta_with_projects("alpha")

    result = run_gap_report(
        tmp_kb, tmp_code_root, meta, severity=Severity.ALWAYS_REQUIRED,
    )
    assert len(result) == 1
    for gap in result[0].gaps:
        assert gap.severity == Severity.ALWAYS_REQUIRED
