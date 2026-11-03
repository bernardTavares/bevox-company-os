"""scanner.py — orchestrator pra retirement-scan.

Scans canonical bevox-knowledge folders (excluding _retired/), runs all
5 detectors per doc, computes compound score. Returns candidates with
score >= 0.7 (per spec §10.3).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCandidate,
)
from lib.knowledge_watcher.retirement.markers import detect_markers
from lib.knowledge_watcher.retirement.code_correlation import detect_code_broken_refs
from lib.knowledge_watcher.retirement.supersession import detect_supersession
from lib.knowledge_watcher.retirement.lifecycle import detect_lifecycle
from lib.knowledge_watcher.retirement.orphan import build_kb_index, detect_orphan
from lib.knowledge_watcher.retirement.scoring import (
    compound_score, is_retirement_candidate,
)
from lib.knowledge_watcher.folder_audit import CANONICAL_FOLDERS


def _doc_type_from_path(rel_path: str) -> str:
    """Derive doc_type from canonical folder prefix.

    '30_adr/...'          → 'adr'
    '10_prd/...'          → 'prd'
    '20_architecture/...' → 'architecture'
    '35_specs/...'        → 'spec'
    '40_roadmap/...'      → 'roadmap'
    '50_releases/...'     → 'release-note'
    '60_customer-feedback/...' → 'customer-feedback'
    '70_metrics/...'      → 'metrics'
    """
    parts = rel_path.split("/", 1)
    if not parts:
        return "unknown"
    folder = parts[0]
    if "_" not in folder:
        return folder
    suffix = folder.split("_", 1)[1]
    # Explicit special cases
    _mapping = {
        "releases": "release-note",
        "specs": "spec",
        "customer-feedback": "customer-feedback",
        "metrics": "metrics",
        "architecture": "architecture",
        "roadmap": "roadmap",
        "prd": "prd",
        "adr": "adr",
        "inbox": "inbox",
    }
    if suffix in _mapping:
        return _mapping[suffix]
    # Generic fallback: strip trailing 's' (pluralise-tolerant)
    if suffix.endswith("s"):
        return suffix[:-1]
    return suffix


def _extract_slug(doc_path: Path, kb_root: Path) -> Optional[str]:
    """`/30_adr/bevox-direct/ADR-X.md` → 'bevox-direct'.
    `/30_adr/_shared/ADR-013.md` → None (treated as cross-project).
    """
    try:
        rel = doc_path.relative_to(kb_root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) < 2:
        return None
    candidate = parts[1]
    if candidate.startswith("_"):
        return None  # _shared, _retired, etc
    return candidate


def scan_retirement_candidates(
    kb_root: Path,
    code_root: Path,
    *,
    project: Optional[str] = None,
    state: Optional[Dict[str, Any]] = None,
) -> List[RetirementCandidate]:
    """Walk canonical, run detectors, return candidates with score >= 0.7.

    If ``state`` is provided, each flagged candidate with a non-None
    project_slug is registered as a GapRecord (F4) via add_gap (idempotent).
    Candidates from ``_shared`` (slug=None) are skipped for gap registration
    since gap_registry requires a concrete repo slug.
    """
    if not kb_root.is_dir():
        return []

    kb_index = build_kb_index(kb_root)

    candidates: List[RetirementCandidate] = []
    for folder in CANONICAL_FOLDERS:
        folder_path = kb_root / folder
        if not folder_path.is_dir():
            continue
        for md in folder_path.rglob("*.md"):
            if "_retired" in md.parts:
                continue
            slug = _extract_slug(md, kb_root)
            if project is not None and slug != project:
                continue

            signals: List[CategorySignal] = []
            signals.extend(detect_markers(md))
            repo_root = code_root / slug if slug else None
            if repo_root and repo_root.is_dir():
                signals.extend(detect_code_broken_refs(md, repo_root))
            signals.extend(detect_supersession(md, md.parent))
            signals.extend(detect_lifecycle(md))
            signals.extend(detect_orphan(md, kb_root, kb_index=kb_index))

            try:
                rel = str(md.relative_to(kb_root))
            except ValueError:
                rel = str(md)
            doc_type = _doc_type_from_path(rel)

            score = compound_score(signals)
            if not is_retirement_candidate(signals, doc_type=doc_type):
                continue

            candidates.append(RetirementCandidate(
                path=md,
                relative_path=rel,
                project_slug=slug,
                score=score,
                signals=signals,
            ))

    if state is not None:
        import json as _json
        from datetime import datetime, timezone
        from lib.knowledge_watcher.gap_registry import (
            GapRecord, GapSource, GapStatus,
            derive_gap_id_f4, add_gap,
        )
        for c in candidates:
            if c.project_slug is None:
                continue  # _shared / no-slug docs: gap_registry requires repo
            gid = derive_gap_id_f4(c.project_slug, c.relative_path)
            doc_type = _doc_type_from_path(c.relative_path)
            # W9.T1 fix: persist signals so /keep, /retire records carry
            # signal_combo into feedback.db.
            signals_payload = [
                {
                    "category": s.category.value,
                    "confidence": s.confidence,
                    "evidence": s.evidence,
                }
                for s in c.signals
            ]
            record = GapRecord(
                gap_id=gid,
                repo=c.project_slug,
                source=GapSource.F4,
                status=GapStatus.OPEN,
                doc_type=doc_type,
                commit_sha=None,
                path=c.relative_path,
                draft_branch=None,
                created_at=datetime.now(timezone.utc),
                snooze_until=None,
                signals_json=_json.dumps(signals_payload),
            )
            add_gap(state, record)

    return candidates
