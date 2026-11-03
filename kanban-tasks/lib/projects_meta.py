"""projects-meta.json read/write atomic helpers.

Spec: bevox-knowledge/35_specs/company-os/2026-04-26-mc-projects-factory.md §3.5
W1 extension: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w1-v1.md
"""
import fcntl
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional


class MetaError(Exception):
    pass


SCHEMA_VERSION = 1

# Capability state machine (per ADR-013).
CAPABILITY_NAMES = (
    "code_repo",
    "knowledge_slot",
    "kanban_sprints",
    "workspace",
    "persona",
    "bot",
    "telegram_topics",
    "mission_control",
)
CAPABILITY_STATES = ("absent", "partial", "provisioned", "drifted")
CAPABILITY_SCHEMA_VERSION = 1

DEFAULT_KNOWLEDGE_WATCHER = {
    "opt_in": True,
    "last_run_at": None,
}

# In-process flag: emit legacy warning at most once per (process, path).
_LEGACY_WARNED: set = set()


def is_knowledge_watcher_opted_in(entry: dict) -> bool:
    """Backward-compat: True if entry lacks the field (default opt-in) OR
    field has opt_in=true. False only if explicitly opt_in=false.
    """
    kw = entry.get("knowledge_watcher")
    if kw is None:
        return True
    return bool(kw.get("opt_in", True))


def get_adr_prefix(slug: str, meta: dict) -> Optional[str]:
    """Read adr_prefix override de projects-meta.

    Path: projects.<slug>.capabilities.knowledge_watcher.adr_prefix.
    Returns None se ausente (auto-detect mode em workflow).
    Handles both dict-keyed schema and list-of-projects schema.

    W5 spec: 35_specs/_shared/2026-05-09-skill-v2-W5-f3-quality-gates-core.md §6.4
    """
    projects = meta.get("projects")
    entry = None
    if isinstance(projects, dict):
        entry = projects.get(slug)
    elif isinstance(projects, list):
        for p in projects:
            if isinstance(p, dict) and (p.get("id") == slug or p.get("slug") == slug):
                entry = p
                break
    if not isinstance(entry, dict):
        return None
    caps = entry.get("capabilities") or {}
    kw = caps.get("knowledge_watcher") or {}
    val = kw.get("adr_prefix")
    return val if isinstance(val, str) and val else None


def read_meta(path: Path) -> dict:
    """Read projects-meta.json. Returns default empty schema if missing.

    Lock-free read (eventually consistent — tolerável pra metadata).
    Emite warning stderr 1× se detectar entries em schema legacy
    (sem capabilities_schema_version).
    """
    if not path.exists():
        return {"version": SCHEMA_VERSION, "projects": {}}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise MetaError(f"failed to read {path}: {e}")
    if is_legacy_meta(data):
        _emit_legacy_warning_once(path)
    return data


def write_meta(path: Path, data: dict) -> None:
    """Atomic write via tmp file + rename. flock pra concurrency.

    Idempotente if data identical to current.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)
    with open(lock_path, "w") as lock_fp:
        fcntl.flock(lock_fp, fcntl.LOCK_EX)
        try:
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            os.replace(tmp, path)
        finally:
            fcntl.flock(lock_fp, fcntl.LOCK_UN)


def insert_project(path: Path, slug: str, entry: dict) -> None:
    """Insert new project entry. Fails if slug already exists."""
    data = read_meta(path)
    if slug in data.get("projects", {}):
        raise MetaError(f"project '{slug}' already exists in meta")
    data.setdefault("projects", {})[slug] = entry
    write_meta(path, data)


def update_project(path: Path, slug: str, partial: dict) -> None:
    """Merge partial dict into existing entry. Fails if slug doesn't exist."""
    data = read_meta(path)
    if slug not in data.get("projects", {}):
        raise MetaError(f"project '{slug}' not found in meta")
    data["projects"][slug].update(partial)
    write_meta(path, data)


def delete_project(path: Path, slug: str) -> None:
    """Remove entry. Fails if slug doesn't exist (paralelo de update_project)."""
    data = read_meta(path)
    if slug not in data.get("projects", {}):
        raise MetaError(f"project '{slug}' not found in meta")
    del data["projects"][slug]
    write_meta(path, data)


# ============ Capability state machine helpers (W1) ============


def is_legacy_entry(entry: dict) -> bool:
    """True if entry is missing capabilities_schema_version (pre-W1 schema)."""
    return not isinstance(entry, dict) or \
        entry.get("capabilities_schema_version") != CAPABILITY_SCHEMA_VERSION


def is_legacy_meta(data: dict) -> bool:
    """True if any project entry is legacy."""
    if not isinstance(data, dict):
        return False
    projects = data.get("projects") or {}
    if not isinstance(projects, dict):
        return False
    return any(is_legacy_entry(e) for e in projects.values())


def empty_capability_set() -> dict:
    """Return a fresh dict with all 8 capabilities at state=absent."""
    return {name: {"state": "absent"} for name in CAPABILITY_NAMES}


def get_capability(meta_or_path, slug: str, capability: str) -> dict:
    """Return capability sub-object for slug or {state: absent} if missing.

    Accepts either a meta dict (already read) or a Path (will read_meta).
    """
    if capability not in CAPABILITY_NAMES:
        raise MetaError(f"unknown capability: {capability}")
    if isinstance(meta_or_path, Path):
        data = read_meta(meta_or_path)
    elif isinstance(meta_or_path, dict):
        data = meta_or_path
    else:
        raise MetaError(
            f"get_capability expects dict or Path; got {type(meta_or_path).__name__}"
        )
    entry = (data.get("projects") or {}).get(slug) or {}
    caps = entry.get("capabilities") or {}
    cap = caps.get(capability)
    if not isinstance(cap, dict):
        return {"state": "absent"}
    return cap


def set_capability_state(
    meta_path: Path,
    slug: str,
    capability: str,
    state: str,
    **fields: Any,
) -> None:
    """Atomic update of capabilities.<capability> sub-object.

    - Validates capability ∈ CAPABILITY_NAMES, state ∈ CAPABILITY_STATES.
    - Merges fields into existing sub-object (preserves keys not passed).
    - Auto-creates capabilities map + capabilities_schema_version if missing
      (idempotent upgrade path for projects in mid-migration).
    - Fails if slug not found in meta.

    Note: param renomeado para meta_path (em vez de path) pra evitar
    colisão com fields={"path": ...} usado por capability code_repo/workspace.
    """
    if capability not in CAPABILITY_NAMES:
        raise MetaError(f"unknown capability: {capability}")
    if state not in CAPABILITY_STATES:
        raise MetaError(f"invalid capability state: {state}")

    data = read_meta(meta_path)
    projects = data.setdefault("projects", {})
    if slug not in projects:
        raise MetaError(f"project '{slug}' not found in meta")
    entry = projects[slug]
    if not isinstance(entry, dict):
        raise MetaError(f"project '{slug}' entry is not a dict")

    entry.setdefault("capabilities_schema_version", CAPABILITY_SCHEMA_VERSION)
    caps = entry.setdefault("capabilities", {})
    cap = caps.setdefault(capability, {})
    cap.update({"state": state, **fields})
    write_meta(meta_path, data)


def _emit_legacy_warning_once(path: Path) -> None:
    """Print 1× per (process, path) warning to stderr if meta has legacy entries."""
    key = str(path.resolve())
    if key in _LEGACY_WARNED:
        return
    _LEGACY_WARNED.add(key)
    print(
        f"warn: {path} contém entries em schema legacy (sem capabilities_schema_version). "
        f"Rode: openclaw project migrate-meta --dry-run",
        file=sys.stderr,
    )
