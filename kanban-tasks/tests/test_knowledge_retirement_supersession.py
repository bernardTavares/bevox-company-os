"""Tests for retirement/supersession.py — Categoria C."""
from pathlib import Path

import pytest

from lib.knowledge_watcher.retirement import RetirementCategory
from lib.knowledge_watcher.retirement.supersession import (
    detect_supersession,
    find_version_successor,
    find_explicit_supersession,
)


def test_no_successor_returns_none(tmp_path):
    p = tmp_path / "doc-v1.md"
    p.write_text("# v1")
    assert find_version_successor(p) is None


def test_v1_with_v2_in_same_dir(tmp_path):
    """v1 + v2 → v1 is superseded."""
    v1 = tmp_path / "feature-v1.md"
    v2 = tmp_path / "feature-v2.md"
    v1.write_text("# v1")
    v2.write_text("# v2")
    successor = find_version_successor(v1)
    assert successor == v2


def test_v1_with_v3_skip_v2(tmp_path):
    """v1 + v3 (no v2) → v1 still superseded by latest."""
    v1 = tmp_path / "feature-v1.md"
    v3 = tmp_path / "feature-v3.md"
    v1.write_text("# v1")
    v3.write_text("# v3")
    successor = find_version_successor(v1)
    assert successor == v3


def test_v2_with_no_v3_no_successor(tmp_path):
    """Standalone v2 with no v3 → no successor for v2."""
    v2 = tmp_path / "feature-v2.md"
    v2.write_text("# v2")
    assert find_version_successor(v2) is None


def test_explicit_supersession_via_substitui(tmp_path):
    """ADR-005 has `**Substitui:** ADR-001` → ADR-001 superseded."""
    adr_dir = tmp_path / "30_adr" / "myslug"
    adr_dir.mkdir(parents=True)
    adr_001 = adr_dir / "ADR-001-foo.md"
    adr_001.write_text("# ADR-001")
    adr_005 = adr_dir / "ADR-005-bar.md"
    adr_005.write_text("""# ADR-005

**Substitui:** ADR-001

## Contexto
""")
    superseded = find_explicit_supersession(adr_001, adr_dir)
    assert superseded is not None
    assert "ADR-005" in str(superseded)


def test_no_explicit_supersession(tmp_path):
    adr_dir = tmp_path / "30_adr" / "myslug"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-001.md").write_text("# ADR-001")
    (adr_dir / "ADR-002.md").write_text("# ADR-002")
    assert find_explicit_supersession(adr_dir / "ADR-001.md", adr_dir) is None


def test_explicit_supersession_case_insensitive_id(tmp_path):
    """`Substitui: adr-001` (lower-case) still matches ADR-001."""
    adr_dir = tmp_path / "30_adr" / "myslug"
    adr_dir.mkdir(parents=True)
    adr_001 = adr_dir / "ADR-001-foo.md"
    adr_001.write_text("# ADR-001")
    successor = adr_dir / "ADR-009.md"
    successor.write_text("# ADR-009\n\nSubstitui: adr-001\n")
    assert find_explicit_supersession(adr_001, adr_dir) is not None


def test_explicit_supersession_ignores_future_tense_prose(tmp_path):
    """`este spec substituirá ADR-001 em wave 2` should NOT trigger.

    Cat C requires the line to start with `Substitui:` (header-style),
    not a future-tense prose mention.
    """
    adr_dir = tmp_path / "30_adr" / "myslug"
    adr_dir.mkdir(parents=True)
    adr_001 = adr_dir / "ADR-001-foo.md"
    adr_001.write_text("# ADR-001")
    successor = adr_dir / "ADR-009.md"
    successor.write_text(
        "# ADR-009\n\nNote: este ADR substituirá ADR-001 em wave 2.\n"
    )
    assert find_explicit_supersession(adr_001, adr_dir) is None


def test_detect_supersession_v1_to_v2(tmp_path):
    v1 = tmp_path / "feature-v1.md"
    v2 = tmp_path / "feature-v2.md"
    v1.write_text("# v1")
    v2.write_text("# v2")
    signals = detect_supersession(v1, tmp_path)
    assert len(signals) == 1
    assert signals[0].category == RetirementCategory.C_SUPERSESSION
    assert signals[0].confidence >= 0.7


def test_detect_supersession_no_signals_when_active(tmp_path):
    """Active v1 alone → no signals."""
    v1 = tmp_path / "feature-v1.md"
    v1.write_text("# v1")
    signals = detect_supersession(v1, tmp_path)
    assert signals == []
