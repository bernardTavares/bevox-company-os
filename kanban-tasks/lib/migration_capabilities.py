"""Migration: legacy flat projects-meta.json schema → capabilities sub-object.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w1-v1.md §Migration
ADR: bevox-knowledge/30_adr/openclaw/ADR-013-project-capability-state-machine.md

CLI: openclaw project migrate-meta [--dry-run]

Idempotente: rerun em entries já migradas é no-op (skip).
Backup: ~/.openclaw/projects-meta.legacy.json escrito 1× (não sobrescreve).
"""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Optional

from lib import projects_meta
from lib.capability_detect import DetectPaths, detect_all


def _build_migrated_entry(
    slug: str,
    legacy_entry: dict,
    paths: DetectPaths,
    *,
    skip_remote: bool = False,
    skip_systemctl: bool = False,
    skip_knowledge: bool = False,
) -> dict:
    """Return a new entry dict with capabilities sub-object populated via
    detect helpers. Preserves all top-level legacy fields (compat readers).
    """
    new_entry = copy.deepcopy(legacy_entry)
    new_entry["capabilities_schema_version"] = (
        projects_meta.CAPABILITY_SCHEMA_VERSION
    )
    new_entry["capabilities"] = detect_all(
        slug, paths, meta_entry=legacy_entry,
        skip_remote=skip_remote, skip_systemctl=skip_systemctl,
        skip_knowledge=skip_knowledge,
    )
    return new_entry


def migrate_meta(
    meta_path: Path,
    *,
    dry_run: bool = False,
    paths: Optional[DetectPaths] = None,
    skip_remote: bool = False,
    skip_systemctl: bool = False,
    skip_knowledge: bool = False,
) -> dict:
    """Migrate projects-meta.json from legacy flat schema to capabilities.

    Returns dict:
      {
        "migrated": ["<slug>", ...],
        "skipped": ["<slug>", ...],   # already migrated
        "diff": {"<slug>": {"before": {...}, "after": {...}}},
        "backup_path": "<path>" | None,
        "dry_run": bool,
      }

    - paths required if any entry needs detection (None falls back to
      defaults rooted at HOME).
    - dry_run=True returns diff without writing or backing up.
    - Backup written 1× per host: if backup file already exists it is
      preserved (rerunning never overwrites previous backup).
    - Idempotent: entries already at capabilities_schema_version=1 are skipped.
    """
    if not meta_path.exists():
        return {
            "migrated": [], "skipped": [], "diff": {},
            "backup_path": None, "dry_run": dry_run,
        }

    if paths is None:
        # Resolve defaults from HOME — most callers pass paths explicitly.
        home = Path.home()
        paths = DetectPaths(
            kb_dir=home / "bevox-knowledge",
            openclaw_dir=home / ".openclaw",
            code_dir=home / "code",
            org="bernardTavares",
        )

    data = projects_meta.read_meta(meta_path)
    projects = (data.get("projects") or {})
    migrated = []
    skipped = []
    diff = {}

    for slug, entry in projects.items():
        if not isinstance(entry, dict):
            skipped.append(slug)
            continue
        if not projects_meta.is_legacy_entry(entry):
            skipped.append(slug)
            continue
        new_entry = _build_migrated_entry(
            slug, entry, paths,
            skip_remote=skip_remote, skip_systemctl=skip_systemctl,
            skip_knowledge=skip_knowledge,
        )
        diff[slug] = {"before": entry, "after": new_entry}
        migrated.append(slug)
        if not dry_run:
            projects[slug] = new_entry

    backup_path = None
    if not dry_run and migrated:
        backup_target = meta_path.with_name(
            meta_path.stem + ".legacy" + meta_path.suffix
        )
        if not backup_target.exists():
            shutil.copy2(meta_path, backup_target)
        backup_path = str(backup_target)
        projects_meta.write_meta(meta_path, data)

    return {
        "migrated": migrated,
        "skipped": skipped,
        "diff": diff,
        "backup_path": backup_path,
        "dry_run": dry_run,
    }
