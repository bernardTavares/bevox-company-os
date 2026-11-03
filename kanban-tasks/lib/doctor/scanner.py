"""Doctor scan phase — drift + orphan + drafts_pending detection.

Pure read-only. No mutations. Spec: W5 §Detect / Orphan detection.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib import projects_meta as _pm
from lib.capability_detect import (
    DetectPaths,
    KNOWLEDGE_FOLDERS,
    detect_all,
)


# Folders inside bevox-knowledge that are NOT slot containers (transversal /
# templates / retired). Mirrors CLAUDE.md §3.1 "Exceções".
KNOWLEDGE_NON_SLOT_DIRS = (
    "_shared",
    "_retired",
    "99_templates",
)

# Profile dirs in $HOME we explicitly never flag as orphans (root install +
# bot pilots that pre-date projects-meta tracking).
BOT_PROFILE_BLACKLIST = (
    ".openclaw",  # root install dir, not a bot profile
)


@dataclass
class DriftRow:
    """One capability drift between declared and detected state."""
    slug: str
    capability: str
    declared_state: str
    detected_state: str
    drift_reason: Optional[str] = None
    declared: Optional[Dict[str, Any]] = None
    detected: Optional[Dict[str, Any]] = None


@dataclass
class OrphanReport:
    """Paths/branches that exist on host but are not registered in meta."""
    code_dirs: List[str] = field(default_factory=list)
    bot_profiles: List[str] = field(default_factory=list)
    workspaces: List[str] = field(default_factory=list)
    bevox_knowledge_slots: List[str] = field(default_factory=list)


@dataclass
class DraftPending:
    """A `draft/<slug>-knowledge-bootstrap` branch awaiting merge."""
    branch: str
    slug: Optional[str]
    age_days: Optional[int] = None


@dataclass
class ScanResult:
    """Aggregated output of scan_all()."""
    projects: Dict[str, Dict[str, Any]]
    drifts: List[DriftRow]
    orphans: OrphanReport
    drafts_pending: List[DraftPending]


def _run_cmd(cmd: list, cwd: Optional[Path] = None, timeout: int = 10) -> tuple:
    """Soft subprocess wrapper. Returns (rc, stdout, stderr); rc=-1 on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return -1, "", ""
    return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()


def _is_drift(declared: Dict[str, Any], detected: Dict[str, Any]) -> bool:
    """True iff declared.state != detected.state, ignoring 'skipped'."""
    det_state = (detected or {}).get("state")
    if det_state in (None, "skipped"):
        return False
    decl_state = (declared or {}).get("state", "absent")
    return decl_state != det_state


def detect_drifts_for_slug(
    slug: str,
    paths: DetectPaths,
    meta_entry: Dict[str, Any],
    *,
    skip_remote: bool = False,
    skip_systemctl: bool = False,
    skip_knowledge: bool = False,
) -> tuple[Dict[str, Dict[str, Any]], List[DriftRow]]:
    """Run detect_all + compare to declared meta. Return (per_cap_dict, drift_list)."""
    detected = detect_all(
        slug, paths, meta_entry=meta_entry,
        skip_remote=skip_remote,
        skip_systemctl=skip_systemctl,
        skip_knowledge=skip_knowledge,
    )
    declared_caps = meta_entry.get("capabilities") or {}
    capabilities_out: Dict[str, Dict[str, Any]] = {}
    drift_rows: List[DriftRow] = []
    for cap, det in detected.items():
        decl = declared_caps.get(cap) or {"state": "absent"}
        decl_state = decl.get("state", "absent")
        det_state = (det or {}).get("state", "absent")
        drift = _is_drift(decl, det)
        cap_payload: Dict[str, Any] = {
            "declared": decl_state,
            "detected": det_state,
            "drift": drift,
        }
        reason = (det or {}).get("drift_reason")
        if drift and not reason:
            reason = f"declared={decl_state}, detected={det_state}"
        if reason:
            cap_payload["drift_reason"] = reason
        capabilities_out[cap] = cap_payload
        if drift:
            drift_rows.append(DriftRow(
                slug=slug,
                capability=cap,
                declared_state=decl_state,
                detected_state=det_state,
                drift_reason=reason,
                declared=decl,
                detected=det,
            ))
    return capabilities_out, drift_rows


# ============ Orphan detection ============

def _safe_iterdir(path: Path) -> List[Path]:
    try:
        return list(path.iterdir())
    except (OSError, PermissionError):
        return []


def detect_orphan_code_dirs(
    paths: DetectPaths,
    declared_slugs: set,
) -> List[str]:
    """Glob ~/code/*/ — list dirs not matching any declared slug.

    Skip dirs without `.git/` (those are not "real" project repos).
    """
    out: List[str] = []
    if not paths.code_dir.is_dir():
        return out
    for child in _safe_iterdir(paths.code_dir):
        if not child.is_dir():
            continue
        if child.name in declared_slugs:
            continue
        if not (child / ".git").exists():
            continue
        out.append(str(child))
    return sorted(out)


def detect_orphan_bot_profiles(
    home: Path,
    declared_bot_areas: set,
) -> List[str]:
    """Glob ~/.openclaw-*/ — list profile dirs not matching any declared bot area.

    Excludes BOT_PROFILE_BLACKLIST.
    """
    out: List[str] = []
    if not home.is_dir():
        return out
    for child in _safe_iterdir(home):
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith(".openclaw-"):
            continue
        suffix = name[len(".openclaw-"):]
        if not suffix:
            continue
        if name in BOT_PROFILE_BLACKLIST:
            continue
        if suffix in declared_bot_areas:
            continue
        out.append(str(child))
    return sorted(out)


def detect_orphan_workspaces(
    paths: DetectPaths,
    declared_slugs: set,
) -> List[str]:
    """Glob ~/.openclaw/workspace-*/ — list dirs not matching any declared slug."""
    out: List[str] = []
    if not paths.openclaw_dir.is_dir():
        return out
    for child in _safe_iterdir(paths.openclaw_dir):
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith("workspace-"):
            continue
        if name == "workspace-template":
            continue  # not a project workspace
        suffix = name[len("workspace-"):]
        if not suffix:
            continue
        if suffix in declared_slugs:
            continue
        out.append(str(child))
    return sorted(out)


def detect_orphan_knowledge_slots(
    paths: DetectPaths,
    declared_slugs: set,
) -> List[str]:
    """Scan bevox-knowledge folders for subdirs that aren't a known slug or
    canonical exception folder.

    Returns paths in '<folder>/<slot>' form (relative to kb_dir).
    """
    out: List[str] = []
    if not paths.kb_dir.is_dir():
        return out
    for folder in KNOWLEDGE_FOLDERS:
        folder_path = paths.kb_dir / folder
        if not folder_path.is_dir():
            continue
        for child in _safe_iterdir(folder_path):
            if not child.is_dir():
                continue
            name = child.name
            if name in KNOWLEDGE_NON_SLOT_DIRS:
                continue
            if name.startswith("_") or name.startswith("."):
                continue
            if name in declared_slugs:
                continue
            out.append(f"{folder}/{name}")
    return sorted(out)


# ============ Drafts pending ============

_BRANCH_RE = re.compile(r"refs/heads/(draft/[^\s]+-knowledge-bootstrap)$")


def detect_drafts_pending(
    paths: DetectPaths,
    declared_slugs: set,
    *,
    runner=_run_cmd,
) -> List[DraftPending]:
    """git ls-remote origin 'refs/heads/draft/*-knowledge-bootstrap'.

    Returns list of DraftPending. Best-effort — if git fails, returns [].
    """
    if not paths.kb_dir.is_dir():
        return []
    rc, stdout, _ = runner(
        ["git", "ls-remote", "origin", "refs/heads/draft/*-knowledge-bootstrap"],
        cwd=paths.kb_dir,
    )
    if rc != 0:
        return []
    out: List[DraftPending] = []
    for line in stdout.splitlines():
        m = _BRANCH_RE.search(line)
        if not m:
            continue
        branch = m.group(1)
        # Extract slug: 'draft/<slug>-knowledge-bootstrap'
        body = branch[len("draft/"):]
        if body.endswith("-knowledge-bootstrap"):
            slug = body[: -len("-knowledge-bootstrap")] or None
        else:
            slug = None
        out.append(DraftPending(branch=branch, slug=slug, age_days=None))
    return out


# ============ Aggregator ============

def scan_all(
    meta_path: Path,
    paths: DetectPaths,
    *,
    skip_remote: bool = False,
    skip_systemctl: bool = False,
    skip_knowledge: bool = False,
    skip_orphans: bool = False,
    skip_drafts: bool = False,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    home: Optional[Path] = None,
) -> ScanResult:
    """Run full scan. Returns ScanResult.

    `include` / `exclude` filter by slug.
    """
    meta = _pm.read_meta(meta_path)
    projects = meta.get("projects") or {}
    all_slugs = set(projects.keys())

    target_slugs = sorted(all_slugs)
    if include:
        inc = set(include)
        target_slugs = [s for s in target_slugs if s in inc]
    if exclude:
        exc = set(exclude)
        target_slugs = [s for s in target_slugs if s not in exc]

    projects_out: Dict[str, Dict[str, Any]] = {}
    drift_rows: List[DriftRow] = []
    for slug in target_slugs:
        entry = projects[slug]
        cap_payload, drifts = detect_drifts_for_slug(
            slug, paths, entry,
            skip_remote=skip_remote,
            skip_systemctl=skip_systemctl,
            skip_knowledge=skip_knowledge,
        )
        projects_out[slug] = {
            "capabilities": cap_payload,
            "drifts": [d.capability for d in drifts],
            "source": entry.get("source"),
        }
        drift_rows.extend(drifts)

    # Orphans use ALL declared slugs (not filtered by include/exclude — orphan
    # is a global concept).
    declared_bot_areas = set()
    for entry in projects.values():
        bot_id = entry.get("bot_id")
        if bot_id:
            declared_bot_areas.add(bot_id)

    if skip_orphans:
        orphans = OrphanReport()
    else:
        home = home or Path(os.environ.get("HOME", str(Path.home())))
        orphans = OrphanReport(
            code_dirs=detect_orphan_code_dirs(paths, all_slugs),
            bot_profiles=detect_orphan_bot_profiles(home, declared_bot_areas),
            workspaces=detect_orphan_workspaces(paths, all_slugs),
            bevox_knowledge_slots=detect_orphan_knowledge_slots(paths, all_slugs),
        )

    drafts_pending: List[DraftPending] = []
    if not skip_drafts and not skip_orphans:
        drafts_pending = detect_drafts_pending(paths, all_slugs)

    return ScanResult(
        projects=projects_out,
        drifts=drift_rows,
        orphans=orphans,
        drafts_pending=drafts_pending,
    )
