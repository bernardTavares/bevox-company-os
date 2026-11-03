"""code_correlation.py — Categoria B (broken code references in canonical doc).

Detects file paths in doc that no longer exist in the project's code repo.
Confidence scales with ratio broken/total references.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)


_INLINE_PATH_RE = re.compile(
    r"`([a-zA-Z0-9_./-]+\.(?:ts|tsx|js|jsx|py|md|yaml|yml|json|sh|sql))`",
)


def extract_referenced_paths(text: str) -> List[str]:
    """Extract list of file paths referenced in inline code spans."""
    paths = []
    for match in _INLINE_PATH_RE.finditer(text):
        p = match.group(1)
        if "://" in p:
            continue
        paths.append(p)
    return paths


def detect_code_broken_refs(doc_path: Path, repo_root: Path) -> List[CategorySignal]:
    """Check referenced paths exist in repo. Flag if substantial broken.

    Threshold: signal raised if total_refs > 0 AND broken_ratio >= 0.5.
    Confidence = scaled with ratio (0.5 base, capped at 0.85).
    """
    if not doc_path.is_file() or not repo_root.is_dir():
        return []
    try:
        content = doc_path.read_text(encoding="utf-8")
    except OSError:
        return []

    refs = extract_referenced_paths(content)
    if not refs:
        return []

    broken = []
    for ref in refs:
        candidate = repo_root / ref
        if not candidate.exists():
            broken.append(ref)

    if not broken:
        return []

    ratio = len(broken) / len(refs)
    if ratio < 0.5:
        return []

    confidence = min(0.5 + (ratio - 0.5) * 0.7, 0.85)
    sample = broken[:3]
    extra = "" if len(broken) <= 3 else f" (+{len(broken) - 3} more)"
    return [CategorySignal(
        category=RetirementCategory.B_CODE_BROKEN,
        confidence=round(confidence, 2),
        evidence=f"{len(broken)}/{len(refs)} refs broken: {', '.join(sample)}{extra}",
    )]
