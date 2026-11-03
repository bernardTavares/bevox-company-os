"""aging.py — Find aging _gaps.md entries; auto-archive after 30d."""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple


_ENTRY_RE = re.compile(r"^- \[ \] \[([a-f0-9]{4,40})\]")


@dataclass
class AgingEntry:
    slug: str
    short_sha: str
    age_days: int
    line: str


def _gaps_md_age_days(gaps_md: Path) -> int:
    """File mtime → age in days (UTC). Approximation; per-line aging is W3.5."""
    if not gaps_md.is_file():
        return 0
    mtime = gaps_md.stat().st_mtime
    delta = datetime.now(timezone.utc).timestamp() - mtime
    return max(0, int(delta // 86400))


def find_aging_drafts(
    kb_root: Path, *, age_days_warn: int = 7, age_days_archive: int = 30,
) -> Tuple[List[AgingEntry], List[AgingEntry]]:
    """Returns (warn_list, archive_list).

    Globs kb_root/00_inbox/*/_gaps.md, parses each line via regex looking
    for `- [ ]` checkbox entries with `[<short>]` short-sha hint. For each
    entry, checks file mtime of the _gaps.md file. (Simplification:
    age = file mtime, not per-line. Per-line aging is W3.5 enhancement.)

    warn_list: age >= age_days_warn AND age < age_days_archive
    archive_list: age >= age_days_archive
    """
    warn: List[AgingEntry] = []
    archive: List[AgingEntry] = []
    inbox = kb_root / "00_inbox"
    if not inbox.is_dir():
        return (warn, archive)

    for slug_dir in inbox.iterdir():
        if not slug_dir.is_dir():
            continue
        gaps_md = slug_dir / "_gaps.md"
        if not gaps_md.is_file():
            continue
        age = _gaps_md_age_days(gaps_md)
        if age < age_days_warn:
            continue
        try:
            content = gaps_md.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            m = _ENTRY_RE.match(line)
            if not m:
                continue
            entry = AgingEntry(
                slug=slug_dir.name, short_sha=m.group(1),
                age_days=age, line=line,
            )
            if age >= age_days_archive:
                archive.append(entry)
            else:
                warn.append(entry)
    return (warn, archive)


def auto_archive_orphaned(
    kb_root: Path, archive_list: List[AgingEntry], *, dry_run: bool = False,
) -> List[Path]:
    """Move draft files for archive entries to _retired/auto/orphaned/.

    detect_flag entries (no draft file) are skipped silently.
    Returns list of moved paths (or would-be-moved paths if dry_run).
    Only archives draft files in 00_inbox/<slug>/ whose filename matches
    `*-{short_sha}-*.md`.
    """
    if not archive_list:
        return []
    target_root = kb_root / "_retired" / "auto" / "orphaned"
    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)

    moved: List[Path] = []
    for entry in archive_list:
        slug_dir = kb_root / "00_inbox" / entry.slug
        if not slug_dir.is_dir():
            continue
        for candidate in slug_dir.glob(f"*-{entry.short_sha}-*.md"):
            today = datetime.now(timezone.utc).date().isoformat()
            target = target_root / f"{today}-{entry.short_sha}.md"
            if dry_run:
                moved.append(target)
                continue
            try:
                shutil.move(str(candidate), str(target))
                moved.append(target)
            except OSError:
                continue
    return moved
