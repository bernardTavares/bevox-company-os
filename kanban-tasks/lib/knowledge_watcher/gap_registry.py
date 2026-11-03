"""gap_registry — GapRecord + helpers for state.json gaps map.

Schema (state.json v2):
  state["repos"][slug]["gaps"]: Dict[gap_id, GapRecord]

ID derivation:
  F1: "<repo>-<commit-short7>-<doctype>"  (e.g., "bevox-direct-a1b2c3d-spec")
  F4: "<repo>-r-<path-hash6>"              (e.g., "bevox-direct-r-3f8a2b")
"""
from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class GapStatus(enum.Enum):
    OPEN = "open"
    SNOOZED = "snoozed"
    DISMISSED = "dismissed"
    ACCEPTED = "accepted"
    RETIRED = "retired"

    @property
    def is_terminal(self) -> bool:
        return self in (GapStatus.DISMISSED, GapStatus.ACCEPTED, GapStatus.RETIRED)


class GapSource(enum.Enum):
    F1 = "f1"
    F4 = "f4"


@dataclass
class GapRecord:
    gap_id: str
    repo: str
    source: GapSource
    status: GapStatus
    doc_type: str
    commit_sha: Optional[str]
    path: str
    draft_branch: Optional[str]
    created_at: datetime
    snooze_until: Optional[datetime]
    # W9.T1 fix: persist F4 signals so /keep, /retire etc can record into
    # feedback.db with real signal_combo data. None for F1 commit gaps
    # (no categorial signals — just commit metadata). JSON-serialized
    # list[{category: str, confidence: float, evidence: str}].
    signals_json: Optional[str] = None


def derive_gap_id_f1(repo: str, commit_sha: str, doc_type: str) -> str:
    """ID determinístico pra F1 commit-watcher gap.

    Formato: <repo>-<commit-short7>-<doctype>
    """
    short = commit_sha[:7]
    return f"{repo}-{short}-{doc_type}"


def derive_gap_id_f4(repo: str, path: str) -> str:
    """ID determinístico pra F4 retirement candidate.

    Formato: <repo>-r-<path-hash6>
    Hash = sha256(path).hexdigest()[:6]
    """
    h = hashlib.sha256(path.encode("utf-8")).hexdigest()[:6]
    return f"{repo}-r-{h}"


# HELPERS: state manipulation


def _serialize_gap(g: GapRecord) -> Dict[str, Any]:
    """Convert GapRecord to dict for JSON serialization."""
    return {
        "gap_id": g.gap_id,
        "repo": g.repo,
        "source": g.source.value,
        "status": g.status.value,
        "doc_type": g.doc_type,
        "commit_sha": g.commit_sha,
        "path": g.path,
        "draft_branch": g.draft_branch,
        "created_at": g.created_at.isoformat().replace("+00:00", "Z"),
        "snooze_until": (
            g.snooze_until.isoformat().replace("+00:00", "Z")
            if g.snooze_until else None
        ),
        "signals_json": g.signals_json,  # W9.T1 fix
    }


def _deserialize_gap(d: Dict[str, Any]) -> GapRecord:
    """Convert dict from state.json back to GapRecord."""
    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    return GapRecord(
        gap_id=d["gap_id"],
        repo=d["repo"],
        source=GapSource(d["source"]),
        status=GapStatus(d["status"]),
        doc_type=d["doc_type"],
        commit_sha=d.get("commit_sha"),
        path=d["path"],
        draft_branch=d.get("draft_branch"),
        created_at=_parse_dt(d["created_at"]) or datetime.now(timezone.utc),
        snooze_until=_parse_dt(d.get("snooze_until")),
        signals_json=d.get("signals_json"),  # W9.T1 fix; None for pre-W9 rows
    )


def _ensure_repo(state: Dict[str, Any], repo: str) -> Dict[str, Any]:
    """Ensure repo entry exists; return its state dict."""
    from .state import default_repo_state

    repos = state.setdefault("repos", {})
    if repo not in repos:
        repos[repo] = default_repo_state()
    return repos[repo]


def add_gap(state: Dict[str, Any], g: GapRecord) -> None:
    """Add gap to state. Idempotent for existing IDs.

    W9.T1 fix: if an existing row has no signals_json but the new record
    has one, backfill it. This lets a re-scan after W9 deploy populate
    signals on legacy v2 gaps without resetting their status/snooze_until.
    """
    rs = _ensure_repo(state, g.repo)
    gaps = rs.setdefault("gaps", {})
    if g.gap_id in gaps:
        existing = gaps[g.gap_id]
        if not existing.get("signals_json") and g.signals_json:
            existing["signals_json"] = g.signals_json
        return
    gaps[g.gap_id] = _serialize_gap(g)


def get_gap(state: Dict[str, Any], gap_id: str) -> Optional[GapRecord]:
    """Retrieve gap by ID; search across all repos. Returns None if not found."""
    for repo, rs in (state.get("repos") or {}).items():
        gaps = rs.get("gaps") or {}
        if gap_id in gaps:
            return _deserialize_gap(gaps[gap_id])
    return None


def update_gap(
    state: Dict[str, Any], gap_id: str, **fields: Any,
) -> bool:
    """Update fields on a gap by ID. Returns True if found and updated."""
    for repo, rs in (state.get("repos") or {}).items():
        gaps = rs.get("gaps") or {}
        if gap_id in gaps:
            d = gaps[gap_id]
            for k, v in fields.items():
                if k == "status" and isinstance(v, GapStatus):
                    d["status"] = v.value
                elif k == "snooze_until" and v is not None:
                    d["snooze_until"] = (
                        v.isoformat().replace("+00:00", "Z")
                        if isinstance(v, datetime) else v
                    )
                elif k == "snooze_until" and v is None:
                    d["snooze_until"] = None
                else:
                    d[k] = v
            return True
    return False


def list_open_gaps(
    state: Dict[str, Any], repo: Optional[str] = None,
) -> List[GapRecord]:
    """List non-terminal gaps. Optional repo filter."""
    out = []
    for r, rs in (state.get("repos") or {}).items():
        if repo and r != repo:
            continue
        for gid, d in (rs.get("gaps") or {}).items():
            g = _deserialize_gap(d)
            if not g.status.is_terminal:
                out.append(g)
    return out
