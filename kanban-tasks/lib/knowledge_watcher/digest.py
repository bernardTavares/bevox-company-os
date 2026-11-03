"""digest.py — idempotency + Telegram digest formatter pra gap-report.

Compares current report against state.json snapshot. Only reports
NEW gaps (avoids spam from same unresolved gaps daily).

Signature = stable hash of (slug, sorted list of (folder, severity)).
"""
from __future__ import annotations

import hashlib
from typing import List

from lib.knowledge_watcher.gap_report import ProjectGapReport, FolderGap


def compute_gap_signature(slug: str, gaps: List[FolderGap]) -> str:
    """Deterministic signature for set of gaps."""
    keys = sorted(f"{g.folder}:{g.severity.value}" for g in gaps)
    payload = f"{slug}|{'|'.join(keys)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def detect_new_gaps(
    reports: List[ProjectGapReport], state: dict,
) -> List[ProjectGapReport]:
    """Return only reports whose signature differs from state.json snapshot."""
    repos = (state or {}).get("repos") or {}
    new = []
    for r in reports:
        sig = compute_gap_signature(r.slug, r.gaps)
        prior = (repos.get(r.slug) or {}).get("last_gap_signature")
        if sig != prior:
            new.append(r)
    return new


def update_state_with_gaps(
    state: dict, reports: List[ProjectGapReport],
) -> dict:
    """Update state.json with new gap signatures (mutates and returns state)."""
    repos = state.setdefault("repos", {})
    for r in reports:
        sig = compute_gap_signature(r.slug, r.gaps)
        repo_state = repos.setdefault(r.slug, {})
        repo_state["last_gap_signature"] = sig
        repo_state["gaps_open"] = len(r.gaps)
    return state
