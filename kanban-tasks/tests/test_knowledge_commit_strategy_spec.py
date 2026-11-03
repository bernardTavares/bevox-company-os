"""Tests for strategies/spec_skeleton.py."""
from pathlib import Path

from lib.knowledge_watcher.commit_watcher import (
    Commit, ClassifierResult, DocType, ClassifierLayer, Strategy,
)
from lib.knowledge_watcher.commit_watcher.strategies.spec_skeleton import (
    apply_spec_skeleton_strategy,
)


def _commit() -> Commit:
    return Commit(
        sha="b"*40, short_sha="b"*7, subject="feat: add template service",
        body="", files_changed=["apps/api/src/services/template.service.ts"],
        diffstat="", author="t", timestamp_iso="2026-05-08T10:00:00Z",
    )


def test_spec_strategy_writes_skeleton_in_inbox(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.SPEC, 0.80, "service file", ClassifierLayer.HEURISTIC)
    draft = apply_spec_skeleton_strategy(
        commit=_commit(), classifier_result=cr,
        slug="myproj", kb_root=kb,
    )
    assert draft.strategy == Strategy.DRAFT_SKELETON
    assert "00_inbox/myproj/" in draft.draft_file_relative
    assert draft.draft_file_relative.endswith("-spec-draft.md")
    written = kb / draft.draft_file_relative
    assert written.exists()


def test_spec_strategy_skeleton_has_six_sections(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.SPEC, 0.80, "x", ClassifierLayer.HEURISTIC)
    draft = apply_spec_skeleton_strategy(
        commit=_commit(), classifier_result=cr,
        slug="p", kb_root=kb,
    )
    body = (kb / draft.draft_file_relative).read_text()
    for header in ["## Contexto", "## Goals", "## Non-goals", "## Approach", "## Acceptance criteria", "## Risks"]:
        assert header in body
    assert "feat: add template service" in body  # subject embedded
    assert "b"*7 in body  # short sha embedded


def test_spec_strategy_dry_run_no_file_written(tmp_path):
    """dry_run=True: GapDraft populated with rel path but no file written."""
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.SPEC, 0.80, "x", ClassifierLayer.HEURISTIC)
    draft = apply_spec_skeleton_strategy(
        commit=_commit(), classifier_result=cr,
        slug="p", kb_root=kb, dry_run=True,
    )
    assert draft.strategy == Strategy.DRAFT_SKELETON
    assert draft.draft_file_relative is not None
    assert not (kb / draft.draft_file_relative).exists()
    assert not (kb / "00_inbox").exists()


def test_spec_strategy_branch_naming(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.SPEC, 0.80, "x", ClassifierLayer.HEURISTIC)
    draft = apply_spec_skeleton_strategy(
        commit=_commit(), classifier_result=cr,
        slug="p", kb_root=kb,
    )
    assert draft.draft_branch.startswith("draft/auto/")
    assert draft.draft_branch.endswith("-spec")
    assert "b"*7 in draft.draft_branch
