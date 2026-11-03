"""supersession.py — Categoria C (newer same-topic doc supersedes this).

Detects:
- Version-naming pattern: `<topic>-v1.md` superseded by `<topic>-v2.md`
- Explicit `**Substitui:** ADR-X` in another doc (in same canonical folder)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional

from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)


_VERSION_RE = re.compile(r"^(.+?)-v(\d+)$")


def find_version_successor(doc_path: Path) -> Optional[Path]:
    """If doc is named `topic-vN.md`, look for `topic-vM.md` with M > N in same dir.

    Returns the highest-version successor, or None.
    """
    if not doc_path.is_file():
        return None
    stem = doc_path.stem
    match = _VERSION_RE.match(stem)
    if not match:
        return None
    base, this_version = match.group(1), int(match.group(2))

    parent = doc_path.parent
    successors = []
    for sibling in parent.glob(f"{base}-v*.md"):
        m = _VERSION_RE.match(sibling.stem)
        if not m:
            continue
        version = int(m.group(2))
        if version > this_version:
            successors.append((version, sibling))
    if not successors:
        return None
    successors.sort()
    return successors[-1][1]


def find_explicit_supersession(doc_path: Path, search_dir: Path) -> Optional[Path]:
    """Look for any other doc in search_dir that has `**Substitui:** <stem-id>`.

    Returns first match (the successor), or None.
    """
    if not doc_path.is_file() or not search_dir.is_dir():
        return None
    target_stem = doc_path.stem
    # Extract identifier (e.g., "ADR-001" from "ADR-001-foo")
    stem_id_match = re.match(r"^([A-Z]+-\d+)", target_stem)
    stem_id = stem_id_match.group(1) if stem_id_match else target_stem

    stem_id_lower = stem_id.lower()
    for sibling in search_dir.iterdir():
        if not sibling.is_file() or sibling.suffix != ".md":
            continue
        if sibling == doc_path:
            continue
        try:
            content = sibling.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            normalized = line.lstrip("> ").lstrip().lstrip("*_").lstrip()
            if not normalized.lower().startswith("substitui"):
                continue
            after = normalized.split(":", 1)
            tail = after[1] if len(after) == 2 else normalized
            if stem_id_lower in tail.lower():
                return sibling
    return None


def detect_supersession(doc_path: Path, search_dir: Path) -> List[CategorySignal]:
    """Detect Cat C signals for doc."""
    signals = []
    successor_v = find_version_successor(doc_path)
    if successor_v is not None:
        signals.append(CategorySignal(
            category=RetirementCategory.C_SUPERSESSION,
            confidence=0.85,
            evidence=f"version successor exists: {successor_v.name}",
        ))
    successor_e = find_explicit_supersession(doc_path, search_dir)
    if successor_e is not None:
        signals.append(CategorySignal(
            category=RetirementCategory.C_SUPERSESSION,
            confidence=0.90,
            evidence=f"explicit Substitui in {successor_e.name}",
        ))
    return signals
