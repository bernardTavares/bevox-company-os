"""folder_audit.py — count canonical content per slot/folder in bevox-knowledge.

Counts non-.gitkeep regular files (recursively, including subfolders like
runbooks/, system-map/, plans/). Returns dict folder → count.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict


# Same as KNOWLEDGE_FOLDERS in capability_detect.py — keep in sync.
CANONICAL_FOLDERS = (
    "00_inbox",
    "10_prd",
    "20_architecture",
    "30_adr",
    "35_specs",
    "40_roadmap",
    "50_releases",
    "60_customer-feedback",
    "70_metrics",
)


def count_canonical_files(path: Path) -> int:
    """Count files under path (recursive), ignoring .gitkeep placeholders.

    Returns 0 if path doesn't exist.
    """
    if not path.is_dir():
        return 0
    count = 0
    for entry in path.rglob("*"):
        if entry.is_file() and entry.name != ".gitkeep":
            count += 1
    return count


def audit_slot(kb_dir: Path, slug: str) -> Dict[str, int]:
    """For a slug, return {folder: file_count} per canonical folder.

    Args:
        kb_dir: bevox-knowledge root path.
        slug: project slug (folder name under each canonical folder).

    Returns:
        Dict with all 9 canonical folders as keys; values = count of
        non-.gitkeep files in `<kb_dir>/<folder>/<slug>/` (recursive).
    """
    result = {}
    for folder in CANONICAL_FOLDERS:
        slot_path = kb_dir / folder / slug
        result[folder] = count_canonical_files(slot_path)
    return result
