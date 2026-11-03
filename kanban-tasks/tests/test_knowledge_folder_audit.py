"""Tests for lib/knowledge_watcher/folder_audit.py."""
from pathlib import Path

import pytest

from lib.knowledge_watcher.folder_audit import (
    count_canonical_files,
    audit_slot,
    CANONICAL_FOLDERS,
)


def test_count_canonical_files_empty_dir(tmp_path):
    """Empty dir → 0 files."""
    d = tmp_path / "empty"
    d.mkdir()
    assert count_canonical_files(d) == 0


def test_count_canonical_files_ignores_gitkeep(tmp_path):
    """Only .gitkeep present → 0 (skip placeholder)."""
    d = tmp_path / "stub"
    d.mkdir()
    (d / ".gitkeep").write_text("")
    assert count_canonical_files(d) == 0


def test_count_canonical_files_counts_md(tmp_path):
    """Real .md files counted."""
    d = tmp_path / "docs"
    d.mkdir()
    (d / "doc1.md").write_text("# doc1")
    (d / "doc2.md").write_text("# doc2")
    (d / ".gitkeep").write_text("")
    assert count_canonical_files(d) == 2


def test_count_canonical_files_recursive(tmp_path):
    """Counts include nested subdirs (e.g. runbooks/)."""
    d = tmp_path / "20_architecture" / "myslug"
    d.mkdir(parents=True)
    (d / "overview.md").write_text("# arch")
    sub = d / "runbooks"
    sub.mkdir()
    (sub / "incident.md").write_text("# incident")
    assert count_canonical_files(d) == 2


def test_count_canonical_files_missing_dir_zero(tmp_path):
    """Non-existent dir → 0."""
    assert count_canonical_files(tmp_path / "doesnt-exist") == 0


def test_audit_slot_full_canonical(tmp_path):
    """audit_slot returns dict folder→count for all canonical folders."""
    kb = tmp_path / "knowledge"
    for folder in CANONICAL_FOLDERS:
        d = kb / folder / "myslug"
        d.mkdir(parents=True)
    (kb / "10_prd" / "myslug" / "prd-v1.md").write_text("# prd")
    (kb / "30_adr" / "myslug" / "ADR-001.md").write_text("# adr")

    result = audit_slot(kb, "myslug")
    assert result["10_prd"] == 1
    assert result["30_adr"] == 1
    assert result["00_inbox"] == 0
    assert result["20_architecture"] == 0
    assert set(result.keys()) == set(CANONICAL_FOLDERS)


def test_audit_slot_missing_slot_all_zero(tmp_path):
    """Slug with no presence → all folders zero."""
    kb = tmp_path / "knowledge"
    for folder in CANONICAL_FOLDERS:
        (kb / folder).mkdir(parents=True)

    result = audit_slot(kb, "nonexistent-slug")
    for folder in CANONICAL_FOLDERS:
        assert result[folder] == 0
