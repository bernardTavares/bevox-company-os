"""gap_report.py — orchestrator pra F2 (gap-report cross-project).

Combina:
- expectations.py (rule per folder per project context)
- project_context.py (signals: age, commits, tags, etc.)
- folder_audit.py (count canonical content per slot)
- projects-meta.json (source of truth: opted-in projects)

Returns list[ProjectGapReport]. Each report contains slug + list of gaps
(folders empty + expected). Optional inputs: project filter, severity filter.

State.json delta detection (idempotência) é responsabilidade do digest
formatter (digest.py) — gap_report.py só produz snapshot atual.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from lib.knowledge_watcher.expectations import (
    folder_expectation, Severity,
)
from lib.knowledge_watcher.folder_audit import audit_slot, CANONICAL_FOLDERS
from lib.knowledge_watcher.project_context import detect_project_context
from lib import projects_meta as _pm


@dataclass
class FolderGap:
    folder: str
    severity: Severity
    canonical_count: int
    reason: str


@dataclass
class ProjectGapReport:
    slug: str
    context: dict = field(default_factory=dict)
    gaps: List[FolderGap] = field(default_factory=list)


def run_gap_report(
    kb_dir: Path,
    code_root: Path,
    meta: dict,
    *,
    project: Optional[str] = None,
    severity: Optional[Severity] = None,
) -> List[ProjectGapReport]:
    """Build list of ProjectGapReport for opted-in projects.

    Args:
        kb_dir: bevox-knowledge root path.
        code_root: ~/code root (each project at <code_root>/<slug>).
        meta: projects-meta.json data (parsed dict).
        project: optional slug filter.
        severity: optional severity filter.

    Returns:
        list[ProjectGapReport] (one per opted-in project, possibly filtered).
    """
    reports: List[ProjectGapReport] = []
    projects = (meta or {}).get("projects") or {}

    for slug, entry in projects.items():
        if project is not None and slug != project:
            continue
        if not _pm.is_knowledge_watcher_opted_in(entry):
            continue

        repo_path = code_root / slug
        ctx = detect_project_context(repo_path, entry)
        counts = audit_slot(kb_dir, slug)

        gaps: List[FolderGap] = []
        for folder in CANONICAL_FOLDERS:
            count = counts.get(folder, 0)
            if count > 0:
                continue  # has content — not a gap
            expectation = folder_expectation(folder, ctx)
            if expectation.severity == Severity.OPTIONAL:
                continue  # not expected — skip
            if severity is not None and expectation.severity != severity:
                continue
            gaps.append(FolderGap(
                folder=folder,
                severity=expectation.severity,
                canonical_count=count,
                reason=expectation.reason,
            ))

        reports.append(ProjectGapReport(slug=slug, context=ctx, gaps=gaps))

    return reports
