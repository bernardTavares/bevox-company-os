"""digest.py — Telegram-ready digest builder for F1 commit watcher."""
from __future__ import annotations

from typing import List

from lib.knowledge_watcher.commit_watcher import GapDraft


def build_digest(slug: str, gaps: List[GapDraft]) -> str:
    """Format gaps as Telegram message body. Empty if no gaps.

    W3.5: usa gap_id (deterministic) em vez de [N] posicional.
    """
    if not gaps:
        return ""
    lines = [f"🌱 [knowledge-watcher] {slug}", f"{len(gaps)} gaps detected:", ""]
    for g in gaps:
        gid = g.gap_id
        lines.append(f"[{gid}] {g.commit.subject} (commit {g.commit.short_sha})")
        lines.append(f"    → {g.digest_line}")
        lines.append(f"    /review {gid} | /dismiss {gid} | /postpone {gid} 7")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_aging_reminder(aging_entries) -> str:
    """Format aging entries as a reminder block (used in digests).

    aging_entries: List[AgingEntry] from aging.py
    """
    if not aging_entries:
        return ""
    lines = ["⏰ Pending review (>= 7 days):"]
    for e in aging_entries:
        lines.append(f"- [{e.short_sha}] ({e.age_days}d old) — {e.line.strip()}")
    return "\n".join(lines) + "\n"
