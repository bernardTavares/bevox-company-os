"""Tests for retirement/orphan.py — Categoria E."""
from pathlib import Path

import pytest

from lib.knowledge_watcher.retirement import RetirementCategory
from lib.knowledge_watcher.retirement.orphan import (
    build_kb_index,
    count_inbound_references,
    detect_orphan,
)


def test_zero_inbound_refs_flags_orphan(tmp_path):
    """Doc with 0 inbound refs in canonical → Cat E signal."""
    kb = tmp_path / "knowledge"
    (kb / "30_adr").mkdir(parents=True)
    target = kb / "30_adr" / "ADR-001-foo.md"
    target.write_text("# ADR-001")
    # No other docs reference ADR-001
    signals = detect_orphan(target, kb)
    assert len(signals) == 1
    assert signals[0].category == RetirementCategory.E_ORPHAN


def test_inbound_ref_present_no_signal(tmp_path):
    """Doc referenced from another canonical doc → no Cat E signal."""
    kb = tmp_path / "knowledge"
    (kb / "30_adr").mkdir(parents=True)
    target = kb / "30_adr" / "ADR-001-foo.md"
    target.write_text("# ADR-001")
    referrer = kb / "30_adr" / "ADR-005.md"
    referrer.write_text("# ADR-005\n\nSee ADR-001 for context.")
    signals = detect_orphan(target, kb)
    assert signals == []


def test_only_retired_refs_still_flags(tmp_path):
    """If only `_retired/` refs to this doc → still orphan (no active refs)."""
    kb = tmp_path / "knowledge"
    (kb / "30_adr").mkdir(parents=True)
    (kb / "_retired" / "old").mkdir(parents=True)
    target = kb / "30_adr" / "ADR-001-foo.md"
    target.write_text("# ADR-001")
    retired_ref = kb / "_retired" / "old" / "old-doc.md"
    retired_ref.write_text("Old refers to ADR-001")
    signals = detect_orphan(target, kb)
    assert len(signals) == 1


def test_count_inbound_zero_when_no_refs(tmp_path):
    kb = tmp_path / "kb"
    (kb / "30_adr").mkdir(parents=True)
    target = kb / "30_adr" / "ADR-001-foo.md"
    target.write_text("# ADR-001")
    assert count_inbound_references(target, kb) == 0


def test_count_inbound_positive_when_referenced(tmp_path):
    kb = tmp_path / "kb"
    (kb / "30_adr").mkdir(parents=True)
    target = kb / "30_adr" / "ADR-001-foo.md"
    target.write_text("# ADR-001")
    other = kb / "30_adr" / "ADR-005.md"
    other.write_text("ref ADR-001-foo")
    third = kb / "30_adr" / "ADR-006.md"
    third.write_text("Also refs ADR-001-foo here")
    assert count_inbound_references(target, kb) == 2


def test_missing_file_returns_empty(tmp_path):
    fake = tmp_path / "nope.md"
    kb = tmp_path / "kb"
    kb.mkdir()
    assert detect_orphan(fake, kb) == []


def test_build_kb_index_excludes_retired(tmp_path):
    kb = tmp_path / "kb"
    (kb / "30_adr").mkdir(parents=True)
    (kb / "_retired" / "old").mkdir(parents=True)
    active = kb / "30_adr" / "ADR-001.md"
    active.write_text("active")
    retired = kb / "_retired" / "old" / "x.md"
    retired.write_text("retired")
    index = build_kb_index(kb)
    assert active in index
    assert retired not in index


def test_count_inbound_with_kb_index_matches_uncached(tmp_path):
    """kb_index path must produce the same result as the rglob path."""
    kb = tmp_path / "kb"
    (kb / "30_adr").mkdir(parents=True)
    target = kb / "30_adr" / "ADR-001-foo.md"
    target.write_text("# ADR-001")
    other = kb / "30_adr" / "ADR-005.md"
    other.write_text("ref ADR-001-foo")
    third = kb / "30_adr" / "ADR-006.md"
    third.write_text("Also refs ADR-001-foo here")
    index = build_kb_index(kb)
    assert count_inbound_references(target, kb, kb_index=index) == 2
    assert count_inbound_references(target, kb) == 2  # backward-compat


def test_detect_orphan_with_kb_index(tmp_path):
    """detect_orphan accepts kb_index and short-circuits FS reads."""
    kb = tmp_path / "kb"
    (kb / "30_adr").mkdir(parents=True)
    target = kb / "30_adr" / "ADR-001-foo.md"
    target.write_text("# ADR-001")
    index = build_kb_index(kb)
    signals = detect_orphan(target, kb, kb_index=index)
    assert len(signals) == 1
    assert signals[0].category == RetirementCategory.E_ORPHAN
