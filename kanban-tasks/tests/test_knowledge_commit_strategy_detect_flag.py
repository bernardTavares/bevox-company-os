"""Tests for strategies/detect_flag.py (entry-only architecture/PRD/roadmap)."""
from lib.knowledge_watcher.commit_watcher import (
    Commit, ClassifierResult, DocType, ClassifierLayer, Strategy,
)
from lib.knowledge_watcher.commit_watcher.strategies.detect_flag import (
    apply_detect_flag_strategy,
)


def _commit() -> Commit:
    return Commit(
        sha="d"*40, short_sha="d"*7, subject="refactor: migrate to event bus",
        body="", files_changed=["a/x.ts", "b/x.ts", "c/x.ts"],
        diffstat="", author="t", timestamp_iso="2026-05-08T10:00:00Z",
    )


def test_detect_flag_no_file_written(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.ARCHITECTURE, 0.66, "cross-module", ClassifierLayer.HEURISTIC)
    draft = apply_detect_flag_strategy(
        commit=_commit(), classifier_result=cr,
        slug="myproj", kb_root=kb, doc_type_label="architecture",
    )
    assert draft.strategy == Strategy.DETECT_FLAG
    assert draft.draft_file_relative is None
    # No file should have been created in kb
    inbox = kb / "00_inbox" / "myproj"
    assert not inbox.exists() or not any(inbox.iterdir())


def test_detect_flag_dry_run_unchanged(tmp_path):
    """dry_run=True: behavior unchanged — no file is ever written by this strategy."""
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.ARCHITECTURE, 0.66, "x", ClassifierLayer.HEURISTIC)
    draft = apply_detect_flag_strategy(
        commit=_commit(), classifier_result=cr,
        slug="myproj", kb_root=kb, doc_type_label="architecture", dry_run=True,
    )
    assert draft.strategy == Strategy.DETECT_FLAG
    assert draft.draft_file_relative is None
    inbox = kb / "00_inbox" / "myproj"
    assert not inbox.exists() or not any(inbox.iterdir())


def test_detect_flag_branch_includes_doctype_label(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.PRD, 0.65, "user-facing", ClassifierLayer.LLM)
    draft = apply_detect_flag_strategy(
        commit=_commit(), classifier_result=cr,
        slug="p", kb_root=kb, doc_type_label="prd",
    )
    assert draft.draft_branch.endswith("-prd")


def test_detect_flag_gaps_entry_format(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.ROADMAP, 0.70, "milestone", ClassifierLayer.LLM)
    draft = apply_detect_flag_strategy(
        commit=_commit(), classifier_result=cr,
        slug="p", kb_root=kb, doc_type_label="roadmap",
    )
    assert "roadmap:" in draft.gaps_entry
    assert "(flagged)" in draft.gaps_entry
    assert "/review" in draft.gaps_entry
