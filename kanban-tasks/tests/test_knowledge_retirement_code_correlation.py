"""Tests for retirement/code_correlation.py — Categoria B."""
from pathlib import Path

import pytest

from lib.knowledge_watcher.retirement import RetirementCategory
from lib.knowledge_watcher.retirement.code_correlation import (
    detect_code_broken_refs,
    extract_referenced_paths,
)


def test_extract_paths_from_inline_code():
    """`apps/api/src/foo.ts` in backticks is extracted."""
    text = "Edit `apps/api/src/foo.ts` to add the new field."
    paths = extract_referenced_paths(text)
    assert "apps/api/src/foo.ts" in paths


def test_extract_paths_ignores_urls():
    text = "See https://github.com/x/y for details."
    paths = extract_referenced_paths(text)
    assert paths == []


def test_extract_paths_extensions_filter():
    text = "`foo.ts`, `bar.py`, `baz.md`, `qux.txt`, `random_word`"
    paths = extract_referenced_paths(text)
    assert "foo.ts" in paths
    assert "bar.py" in paths
    assert "baz.md" in paths
    assert "qux.txt" not in paths
    assert "random_word" not in paths


def test_no_broken_refs_when_all_exist(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "foo.ts").write_text("// real")
    doc = tmp_path / "doc.md"
    doc.write_text("Edit `src/foo.ts` to fix it.")

    signals = detect_code_broken_refs(doc, repo)
    assert signals == []


def test_broken_ref_flagged(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    doc = tmp_path / "doc.md"
    doc.write_text("Edit `apps/api/src/removed.ts` for behavior X.")

    signals = detect_code_broken_refs(doc, repo)
    assert len(signals) == 1
    assert signals[0].category == RetirementCategory.B_CODE_BROKEN
    assert signals[0].confidence >= 0.5
    assert "removed.ts" in signals[0].evidence


def test_partial_broken_refs(tmp_path):
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "ok.ts").write_text("// real")
    doc = tmp_path / "doc.md"
    doc.write_text("Edit `src/ok.ts` and `src/broken.ts` and `src/dead.ts`.")

    signals = detect_code_broken_refs(doc, repo)
    assert len(signals) == 1
    assert 0.5 <= signals[0].confidence <= 0.85


def test_repo_missing_returns_empty(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("`some/path.ts`")
    fake_repo = tmp_path / "no-repo"
    assert detect_code_broken_refs(doc, fake_repo) == []
