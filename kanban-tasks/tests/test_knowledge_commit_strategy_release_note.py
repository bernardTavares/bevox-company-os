"""Tests for strategies/release_note.py."""
import subprocess
from pathlib import Path

from lib.knowledge_watcher.commit_watcher import (
    Commit, ClassifierResult, DocType, ClassifierLayer, Strategy,
)
from lib.knowledge_watcher.commit_watcher.strategies.release_note import (
    apply_release_note_strategy,
)


def _make_repo_with_history(tmp_path: Path) -> tuple[Path, str]:
    """Returns (repo_root, release_commit_sha)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)

    last_sha = ""
    for msg in ["feat: add A", "fix: B", "refactor: C", "release: v1.0.0"]:
        slug = msg.split()[1]
        (repo / f"{slug}.txt").write_text(msg)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
        )
        last_sha = out.stdout.strip()
    return repo, last_sha


def test_release_strategy_creates_filled_draft(tmp_path):
    repo, release_sha = _make_repo_with_history(tmp_path)
    kb = tmp_path / "kb"
    kb.mkdir()

    commit = Commit(
        sha=release_sha, short_sha=release_sha[:7],
        subject="release: v1.0.0", body="",
        files_changed=["release.txt"], diffstat="",
        author="t", timestamp_iso="2026-05-08T10:00:00Z",
    )
    cr = ClassifierResult(DocType.RELEASE_NOTE, 0.95, "release prefix", ClassifierLayer.HEURISTIC)

    draft = apply_release_note_strategy(
        commit=commit, classifier_result=cr,
        repo_root=repo, slug="myproj", kb_root=kb,
    )

    assert draft.strategy == Strategy.DRAFT_FILLED
    assert draft.draft_branch.startswith("draft/auto/")
    assert "release-note" in draft.draft_branch
    assert draft.draft_file_relative is not None
    assert "50_releases/myproj/" in draft.draft_file_relative
    assert draft.draft_file_relative.endswith("1.0.0.md")

    written = kb / draft.draft_file_relative
    assert written.exists()
    body = written.read_text()
    assert "Features" in body
    assert "feat: add A" in body
    assert "Fixes" in body
    assert "fix: B" in body
    assert "Refactors" in body
    assert "release: v1.0.0" not in body  # release commit itself excluded


def test_release_strategy_dry_run_no_file_written(tmp_path):
    """dry_run=True: GapDraft populated with rel path but no file written to kb."""
    repo, sha = _make_repo_with_history(tmp_path)
    kb = tmp_path / "kb"
    kb.mkdir()

    commit = Commit(
        sha=sha, short_sha=sha[:7],
        subject="release: v1.0.0", body="",
        files_changed=["release.txt"], diffstat="",
        author="t", timestamp_iso="2026-05-08T10:00:00Z",
    )
    cr = ClassifierResult(DocType.RELEASE_NOTE, 0.95, "x", ClassifierLayer.HEURISTIC)
    draft = apply_release_note_strategy(
        commit=commit, classifier_result=cr,
        repo_root=repo, slug="myproj", kb_root=kb, dry_run=True,
    )
    assert draft.strategy == Strategy.DRAFT_FILLED
    assert draft.draft_file_relative is not None  # path computed
    # but NO file written
    assert not (kb / draft.draft_file_relative).exists()
    # and the parent dir is not created
    assert not (kb / "50_releases").exists()


def test_release_strategy_no_version_falls_back_to_date(tmp_path):
    """If subject has no v\d.\d.\d, version = today's date."""
    repo, sha = _make_repo_with_history(tmp_path)
    kb = tmp_path / "kb"
    kb.mkdir()

    commit = Commit(
        sha=sha, short_sha=sha[:7],
        subject="release: hotfix", body="",
        files_changed=[], diffstat="",
        author="t", timestamp_iso="2026-05-08T10:00:00Z",
    )
    cr = ClassifierResult(DocType.RELEASE_NOTE, 0.95, "x", ClassifierLayer.HEURISTIC)
    draft = apply_release_note_strategy(
        commit=commit, classifier_result=cr,
        repo_root=repo, slug="p", kb_root=kb,
    )
    # version should be YYYY.MM.DD
    assert draft.draft_file_relative.endswith(".md")
    # date format check: file stem should be like "2026.05.08"
    fname = Path(draft.draft_file_relative).stem
    assert len(fname.split(".")) == 3
