"""orphan.py — Categoria E (0 inbound canonical references)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from lib.knowledge_watcher.retirement import (
    CategorySignal, RetirementCategory,
)

_STEM_ID_RE = re.compile(r"^([A-Z]+-\d+)", re.ASCII)


def _search_terms(doc_path: Path) -> List[str]:
    """Return the set of strings to look for when searching for inbound refs.

    Includes:
    - Full stem (e.g. ``ADR-001-foo``)
    - Canonical short ID if the stem starts with an uppercase-letter+dash+digits
      pattern (e.g. ``ADR-001``)
    - Filename with extension (e.g. ``ADR-001-foo.md``)
    """
    stem = doc_path.stem
    terms = [stem, doc_path.name]
    m = _STEM_ID_RE.match(stem)
    if m:
        short_id = m.group(1)
        if short_id != stem:
            terms.append(short_id)
    return terms


def build_kb_index(kb_root: Path) -> Dict[Path, str]:
    """One-shot read of all canonical .md files (excluding _retired/).

    Use this in the scanner orchestrator and pass to ``detect_orphan`` /
    ``count_inbound_references`` to avoid O(n²) FS reads when scanning many
    docs. Each file is read at most once per scan.
    """
    if not kb_root.is_dir():
        return {}
    index: Dict[Path, str] = {}
    for md in kb_root.rglob("*.md"):
        if "_retired" in md.parts:
            continue
        try:
            index[md] = md.read_text(encoding="utf-8")
        except OSError:
            continue
    return index


def count_inbound_references(
    doc_path: Path,
    kb_root: Path,
    *,
    kb_index: Optional[Dict[Path, str]] = None,
) -> int:
    """Count files in kb_root (excluding _retired/) that reference doc_path.

    A reference is detected when any of the doc's identifiers (full stem,
    canonical short ID, or filename) appears in the content of another active
    canonical document.

    Excludes:
    - The doc itself
    - Any path containing a ``_retired/`` component

    If ``kb_index`` is provided (built once via ``build_kb_index``), it is used
    instead of re-reading every file. Otherwise falls back to per-call rglob.
    """
    if not doc_path.is_file() or not kb_root.is_dir():
        return 0
    terms = _search_terms(doc_path)

    if kb_index is not None:
        count = 0
        for md, content in kb_index.items():
            if md == doc_path:
                continue
            if any(t in content for t in terms):
                count += 1
        return count

    count = 0
    for md in kb_root.rglob("*.md"):
        if md == doc_path:
            continue
        if "_retired" in md.parts:
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(t in content for t in terms):
            count += 1
    return count


def detect_orphan(
    doc_path: Path,
    kb_root: Path,
    *,
    kb_index: Optional[Dict[Path, str]] = None,
) -> List[CategorySignal]:
    """Cat E: zero inbound references from active canonical docs."""
    if not doc_path.is_file() or not kb_root.is_dir():
        return []
    refs = count_inbound_references(doc_path, kb_root, kb_index=kb_index)
    if refs == 0:
        return [CategorySignal(
            category=RetirementCategory.E_ORPHAN,
            confidence=0.4,
            evidence="0 inbound references from active canonical docs",
        )]
    return []
