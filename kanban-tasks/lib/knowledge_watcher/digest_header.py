"""Compact summary header for F2/F4 Telegram digests (W8.T1.3).

Reduces scrollwall: counts + breakdown by score / project / doc-type top-N.
Designed to fit under ~500 chars so the main body still has room before the
Telegram 4096 chunking limit kicks in.

Generic over input type — works for F4 RetirementCandidate (has score) and
F2 flattened gap rows (score=None). Caller passes attribute names for
project + path + (optional) score.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, List, Optional


_HIGH_SCORE = 1.0
_MID_SCORE = 0.7


def _doc_type_from_path(rel_path: str) -> str:
    """'30_adr/...' → 'adr'. Mirrors scanner._doc_type_from_path."""
    parts = rel_path.split("/", 1)
    if not parts or "_" not in parts[0]:
        return "other"
    suffix = parts[0].split("_", 1)[1]
    mapping = {
        "adr": "adr",
        "prd": "prd",
        "specs": "spec",
        "spec": "spec",
        "architecture": "architecture",
        "roadmap": "roadmap",
        "releases": "release-note",
        "inbox": "inbox",
        "customer-feedback": "customer-feedback",
        "metrics": "metrics",
    }
    if suffix in mapping:
        return mapping[suffix]
    return suffix.rstrip("s") if suffix.endswith("s") else suffix


def format_summary_header(
    items: List[Any],
    *,
    title: str,
    score_attr: Optional[str] = "score",
    project_attr: str = "project_slug",
    path_attr: str = "relative_path",
    top_n: int = 3,
) -> str:
    """Build a compact summary header for digest dispatch.

    Lines:
      <title>
      Total: <n>
      Por score: 🔴 X score 1.0 · 🟡 Y score 0.7-0.99   (skipped if score_attr=None)
      Por projeto: p1 N (X%), p2 N (X%), ...
      Por doc-type: adr N, spec N, ...
      ─────
    """
    n = len(items)
    if n == 0:
        return f"{title}\nTotal: 0\n─────"

    lines = [title, f"Total: {n}"]

    if score_attr and any(
        getattr(i, score_attr, None) is not None for i in items
    ):
        high = sum(
            1 for i in items
            if (getattr(i, score_attr, 0.0) or 0.0) >= _HIGH_SCORE
        )
        mid = sum(
            1 for i in items
            if _MID_SCORE <= (getattr(i, score_attr, 0.0) or 0.0) < _HIGH_SCORE
        )
        lines.append(f"Por score: 🔴 {high} score 1.0 · 🟡 {mid} score 0.7-0.99")

    proj_counts = Counter(
        (getattr(i, project_attr, None) or "_unknown") for i in items
    )
    proj_summary = ", ".join(
        f"{p} {c} ({c * 100 // n}%)"
        for p, c in proj_counts.most_common(top_n)
    )
    if proj_summary:
        lines.append(f"Por projeto: {proj_summary}")

    type_counts = Counter(
        _doc_type_from_path(getattr(i, path_attr, "") or "") for i in items
    )
    type_summary = ", ".join(
        f"{t} {c}" for t, c in type_counts.most_common(top_n + 2)
    )
    if type_summary:
        lines.append(f"Por doc-type: {type_summary}")

    lines.append("─────")
    return "\n".join(lines)
