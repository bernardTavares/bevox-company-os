"""Tests for strategies/adr_template.py."""
from lib.knowledge_watcher.commit_watcher import (
    Commit, ClassifierResult, DocType, ClassifierLayer, Strategy,
)
from lib.knowledge_watcher.commit_watcher.strategies.adr_template import (
    apply_adr_template_strategy, _topic_hint,
)


def _commit(files=None) -> Commit:
    return Commit(
        sha="c"*40, short_sha="c"*7, subject="feat: add tenant model",
        body="", files_changed=files or ["prisma/schema.prisma"],
        diffstat="", author="t", timestamp_iso="2026-05-08T10:00:00Z",
    )


def test_adr_strategy_writes_template_in_inbox(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.ADR, 0.78, "schema change", ClassifierLayer.HEURISTIC)
    draft = apply_adr_template_strategy(
        commit=_commit(), classifier_result=cr,
        slug="myproj", kb_root=kb,
    )
    assert draft.strategy == Strategy.DETECT_FLAG_TEMPLATE
    assert draft.draft_file_relative.endswith("-adr-template.md")
    assert "00_inbox/myproj/" in draft.draft_file_relative
    body = (kb / draft.draft_file_relative).read_text()
    assert "## Contexto" in body
    assert "## Decisão" in body
    assert "## Alternativas consideradas" in body
    assert "## Consequências" in body


def test_adr_strategy_dry_run_no_file_written(tmp_path):
    """dry_run=True: GapDraft populated with rel path but no file written."""
    kb = tmp_path / "kb"
    kb.mkdir()
    cr = ClassifierResult(DocType.ADR, 0.78, "x", ClassifierLayer.HEURISTIC)
    draft = apply_adr_template_strategy(
        commit=_commit(), classifier_result=cr,
        slug="p", kb_root=kb, dry_run=True,
    )
    assert draft.strategy == Strategy.DETECT_FLAG_TEMPLATE
    assert draft.draft_file_relative is not None
    assert not (kb / draft.draft_file_relative).exists()
    assert not (kb / "00_inbox").exists()


def test_topic_hint_detects_schema():
    c = _commit(files=["prisma/schema.prisma"])
    assert "schema" in _topic_hint(c)


def test_topic_hint_detects_auth():
    c = _commit(files=["apps/api/middleware/auth/jwt.ts"])
    assert "auth" in _topic_hint(c)


def test_topic_hint_falls_back_to_general():
    c = _commit(files=["src/foo/bar.ts"])
    assert "general" in _topic_hint(c)
