"""Tests for commit_watcher/aging.py."""
import os
import time
from pathlib import Path

from lib.knowledge_watcher.commit_watcher.aging import (
    find_aging_drafts, auto_archive_orphaned, AgingEntry,
)


def _make_gaps_md(kb_root: Path, slug: str, lines: list[str], age_days: int) -> Path:
    """Create _gaps.md with given content; backdate mtime."""
    target = kb_root / "00_inbox" / slug / "_gaps.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n")
    if age_days > 0:
        backdate = time.time() - age_days * 86400
        os.utime(target, (backdate, backdate))
    return target


def test_find_aging_no_gaps_md_returns_empty(tmp_path):
    kb = tmp_path / "kb"; kb.mkdir()
    warn, arch = find_aging_drafts(kb)
    assert warn == [] and arch == []


def test_find_aging_recent_returns_empty(tmp_path):
    kb = tmp_path / "kb"
    _make_gaps_md(kb, "p", ["- [ ] [aaa1111] spec: x"], age_days=2)
    warn, arch = find_aging_drafts(kb)
    assert warn == [] and arch == []


def test_find_aging_warns_at_7_days(tmp_path):
    kb = tmp_path / "kb"
    _make_gaps_md(kb, "p", ["- [ ] [aaa1111] spec: x"], age_days=10)
    warn, arch = find_aging_drafts(kb)
    assert len(warn) == 1
    assert warn[0].slug == "p"
    assert warn[0].short_sha == "aaa1111"
    assert arch == []


def test_find_aging_archives_at_30_days(tmp_path):
    kb = tmp_path / "kb"
    _make_gaps_md(kb, "p", ["- [ ] [bbb2222] adr: y"], age_days=35)
    warn, arch = find_aging_drafts(kb)
    assert warn == []
    assert len(arch) == 1
    assert arch[0].short_sha == "bbb2222"


def test_auto_archive_moves_files(tmp_path):
    kb = tmp_path / "kb"
    _make_gaps_md(kb, "p", ["- [ ] [ccc3333] spec: z"], age_days=35)
    # create draft file matching short
    draft = kb / "00_inbox" / "p" / "2026-04-01-ccc3333-spec-draft.md"
    draft.write_text("draft body")

    _, arch = find_aging_drafts(kb)
    moved = auto_archive_orphaned(kb, arch)
    assert len(moved) == 1
    assert not draft.exists()
    archived = kb / "_retired" / "auto" / "orphaned"
    assert archived.is_dir()
    assert any(p.suffix == ".md" for p in archived.iterdir())


def test_auto_archive_dry_run_no_move(tmp_path):
    kb = tmp_path / "kb"
    _make_gaps_md(kb, "p", ["- [ ] [ddd4444] spec: q"], age_days=35)
    draft = kb / "00_inbox" / "p" / "2026-04-01-ddd4444-spec-draft.md"
    draft.write_text("draft body")
    _, arch = find_aging_drafts(kb)
    moved = auto_archive_orphaned(kb, arch, dry_run=True)
    assert len(moved) == 1
    assert draft.exists()  # NOT moved
