"""state.py — read/write ~/.openclaw/knowledge-watcher/state.json.

Schema (version 2):
{
  "version": 2,
  "repos": {
    "<slug>": {
      "last_commit_processed": "<sha>" | null,
      "last_run_at": "<iso8601>" | null,
      "gaps_open": <int>,
      "gaps_dismissed_total": <int>,
      "retirement_keep_until": {"<doc-path>": "<iso8601>"},
      "gaps": {"<gap_id>": <GapRecord serialized>}
    }
  },
  "global": {
    "last_full_audit_at": "<iso8601>" | null,
    "f1_telegram_digest_seq": <int>
  }
}

Idempotent: read returns default if file missing. Writes are atomic
via temp-file rename (lock-free is acceptable; cron is single-writer).

Migration: v1 state.json files are treated as invalid version and loaded
as v2 default (empty state). Backfill happens in P1.T1.8 via re-audit.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict


SCHEMA_VERSION = 2


def default_state() -> Dict[str, Any]:
    """Return empty state skeleton."""
    return {
        "version": SCHEMA_VERSION,
        "repos": {},
        "global": {
            "last_full_audit_at": None,
            "f1_telegram_digest_seq": 0,
        },
    }


def default_repo_state() -> Dict[str, Any]:
    """Return empty repo state skeleton."""
    return {
        "last_commit_processed": None,
        "last_run_at": None,
        "gaps_open": 0,
        "gaps_dismissed_total": 0,
        "retirement_keep_until": {},
        "gaps": {},  # NEW v2: gap_id → GapRecord serialized dict
    }


def read_state(path: Path) -> Dict[str, Any]:
    """Read state.json; return default skeleton if file missing.

    Defensive: invalid JSON also returns default (caller can detect via
    last_full_audit_at being None on long-running cron).
    """
    if not path.is_file():
        return default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    if not isinstance(data, dict) or data.get("version") != SCHEMA_VERSION:
        return default_state()
    return data


def write_state(path: Path, data: Dict[str, Any]) -> None:
    """Atomic write via temp-file + rename. Creates parent dirs if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=str(path.parent), prefix=".state-", suffix=".tmp",
        delete=False, encoding="utf-8",
    ) as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def get_repo_state(state: Dict[str, Any], slug: str) -> Dict[str, Any]:
    """Return repo state for slug; default skeleton if absent."""
    repos = state.setdefault("repos", {})
    if slug not in repos:
        return default_repo_state()
    # Merge with default to fill any missing keys (forward-compat)
    merged = default_repo_state()
    merged.update(repos[slug])
    return merged


def set_repo_state(
    state: Dict[str, Any], slug: str, fields: Dict[str, Any],
) -> None:
    """Merge fields into repo state. Creates entry if absent."""
    repos = state.setdefault("repos", {})
    current = repos.get(slug) or default_repo_state()
    current.update(fields)
    repos[slug] = current
