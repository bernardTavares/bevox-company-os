"""Tests for git_ops — git operations for skill-V2 W3.5."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib.knowledge_watcher.git_ops import (
    commit_in_draft_branch, branch_url,
    move_to_retired, ff_merge_to_main,
)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# init\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)


def test_commit_in_draft_branch_creates_branch_and_commits(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    target = repo / "doc.md"
    target.write_text("# doc\n\nhello.\n")
    sha = commit_in_draft_branch(
        repo, "draft/test-branch", "doc.md",
        "test commit", push=False,
    )
    # Verify branch exists
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=repo,
        capture_output=True, text=True,
    ).stdout
    assert "draft/test-branch" in branches
    # SHA returned matches HEAD on that branch
    head = subprocess.run(
        ["git", "rev-parse", "draft/test-branch"], cwd=repo,
        capture_output=True, text=True,
    ).stdout.strip()
    assert sha == head
    # Original branch (main) restored
    cur = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo,
        capture_output=True, text=True,
    ).stdout.strip()
    assert cur == "main"


def test_commit_in_draft_branch_idempotent_on_no_changes(tmp_path):
    """commit --allow-empty mas no second call, ainda OK."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    target = repo / "doc.md"
    target.write_text("# doc\n")
    sha1 = commit_in_draft_branch(repo, "draft/test", "doc.md", "msg1", push=False)
    # Second commit on same branch — no file change, still creates new commit (allow-empty)
    sha2 = commit_in_draft_branch(repo, "draft/test", "doc.md", "msg2", push=False)
    assert sha1 != sha2  # new commit


def test_branch_url():
    url = branch_url("https://github.com/Bevox/bevox-knowledge.git", "draft/test")
    assert url == "https://github.com/Bevox/bevox-knowledge/tree/draft/test"
    # Trailing slash
    url2 = branch_url("https://github.com/Bevox/bevox-knowledge/", "draft/x")
    assert url2 == "https://github.com/Bevox/bevox-knowledge/tree/draft/x"


# ---------------------------------------------------------------------------
# T2.6 — move_to_retired
# ---------------------------------------------------------------------------

def test_move_to_retired_moves_file_in_draft_branch(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    src_dir = repo / "30_adr" / "bevox-direct"
    src_dir.mkdir(parents=True)
    src_file = src_dir / "ADR-001.md"
    src_file.write_text("# ADR-001\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add adr"], cwd=repo, check=True, capture_output=True)

    sha = move_to_retired(
        repo, "30_adr/bevox-direct/ADR-001.md",
        "_retired/bevox-direct/adr/2026-05-09-ADR-001.md",
        "draft/auto/retire-test", push=False,
    )
    # Verify on draft branch: src removed, dest exists
    subprocess.run(["git", "checkout", "draft/auto/retire-test"], cwd=repo, check=True, capture_output=True)
    assert not (repo / "30_adr/bevox-direct/ADR-001.md").is_file()
    assert (repo / "_retired/bevox-direct/adr/2026-05-09-ADR-001.md").is_file()
    # Restore main for cleanup
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
    # Original file on main was untouched
    assert (repo / "30_adr/bevox-direct/ADR-001.md").is_file()


def test_move_to_retired_returns_valid_sha(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    src_dir = repo / "30_adr" / "bevox-direct"
    src_dir.mkdir(parents=True)
    (src_dir / "ADR-002.md").write_text("# ADR-002\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add adr002"], cwd=repo, check=True, capture_output=True)

    sha = move_to_retired(
        repo, "30_adr/bevox-direct/ADR-002.md",
        "_retired/bevox-direct/adr/2026-05-09-ADR-002.md",
        "draft/auto/retire-adr002", push=False,
    )
    assert len(sha) == 40  # full SHA
    # Verify SHA matches HEAD on draft branch
    head = subprocess.run(
        ["git", "rev-parse", "draft/auto/retire-adr002"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    assert sha == head
    # Working tree restored to main
    cur = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    assert cur == "main"


# ---------------------------------------------------------------------------
# T2.7 — ff_merge_to_main
# ---------------------------------------------------------------------------

def test_ff_merge_to_main_advances_main(tmp_path):
    repo = tmp_path / "repo"
    _init_repo(repo)
    # Create draft branch with new commit
    subprocess.run(["git", "checkout", "-b", "draft/test"], cwd=repo, check=True, capture_output=True)
    (repo / "release.md").write_text("# release\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "release"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)

    sha = ff_merge_to_main(repo, "draft/test", push=False)
    # main now has release commit
    log = subprocess.run(
        ["git", "log", "--oneline", "main"], cwd=repo,
        capture_output=True, text=True,
    ).stdout
    assert "release" in log
    head = subprocess.run(
        ["git", "rev-parse", "main"], cwd=repo,
        capture_output=True, text=True,
    ).stdout.strip()
    assert sha == head


def test_ff_merge_fails_when_not_ffable(tmp_path):
    """If main diverged, FF-merge fails with RuntimeError."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    # Create draft from main
    subprocess.run(["git", "checkout", "-b", "draft/x"], cwd=repo, check=True, capture_output=True)
    (repo / "draft.md").write_text("# draft\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "draft"], cwd=repo, check=True, capture_output=True)
    # Diverge main
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True, capture_output=True)
    (repo / "diverge.md").write_text("# diverge\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "diverge"], cwd=repo, check=True, capture_output=True)

    with pytest.raises(RuntimeError, match="FF-merge"):
        ff_merge_to_main(repo, "draft/x", push=False)
