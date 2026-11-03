"""Tests for commit_watcher/digest.py."""
from lib.knowledge_watcher.commit_watcher import (
    Commit, ClassifierResult, DocType, ClassifierLayer, Strategy, GapDraft,
)
from lib.knowledge_watcher.commit_watcher.digest import (
    build_digest, build_aging_reminder,
)
from lib.knowledge_watcher.commit_watcher.aging import AgingEntry


def _gap(short_sha="a1b2c3d", subject="feat: x") -> GapDraft:
    commit = Commit(
        sha="x"*40, short_sha=short_sha, subject=subject, body="",
        files_changed=[], diffstat="", author="t",
        timestamp_iso="2026-05-08T10:00:00Z",
    )
    cr = ClassifierResult(DocType.SPEC, 0.80, "x", ClassifierLayer.HEURISTIC)
    return GapDraft(
        project_slug="p", commit=commit, classifier_result=cr,
        strategy=Strategy.DRAFT_SKELETON, draft_branch="draft/auto/x",
        draft_file_relative="00_inbox/p/x.md",
        gaps_entry=f"- [ ] [{short_sha}] spec: {subject}",
        digest_line=f"{short_sha} {subject} → spec missing | confidence: 0.80 (heuristic)",
    )


def test_build_digest_empty_returns_empty():
    assert build_digest("p", []) == ""


def test_build_digest_includes_count_and_subjects():
    gaps = [_gap("aaa1111", "feat: A"), _gap("bbb2222", "fix: B")]
    out = build_digest("myproj", gaps)
    assert "knowledge-watcher" in out
    assert "myproj" in out
    assert "2 gaps detected" in out
    assert "feat: A" in out
    assert "fix: B" in out
    # W3.5: commands use gap_id (deterministic), not positional [N]
    for g in gaps:
        gid = g.gap_id
        assert f"/review {gid}" in out
        assert f"/dismiss {gid}" in out
        assert f"/postpone {gid}" in out


def test_build_digest_uses_gap_id_in_commands():
    """W3.5: build_digest emits gap_id in /dismiss /review /postpone commands."""
    gaps = [_gap("a1b2c3d", "feat: foo")]
    out = build_digest("myproj", gaps)
    expected_id = gaps[0].gap_id
    assert f"[{expected_id}]" in out
    assert f"/review {expected_id}" in out
    assert f"/dismiss {expected_id}" in out
    assert f"/postpone {expected_id}" in out


def test_build_aging_reminder_empty_returns_empty():
    assert build_aging_reminder([]) == ""


def test_build_aging_reminder_lists_entries():
    entries = [
        AgingEntry(slug="p", short_sha="aaa1111", age_days=10,
                   line="- [ ] [aaa1111] spec: feat foo"),
    ]
    out = build_aging_reminder(entries)
    assert "Pending review" in out
    assert "aaa1111" in out
    assert "10d" in out
