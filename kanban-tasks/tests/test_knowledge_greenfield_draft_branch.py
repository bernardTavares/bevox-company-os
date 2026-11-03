"""Tests for greenfield draft_branch.push_to_draft_branch."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest

from lib.knowledge_watcher.greenfield.draft_branch import (
    push_to_draft_branch, DraftBranchResult,
)


def _git(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def kb_repo(tmp_path: Path) -> Path:
    """Create a fresh git repo with one commit on `main`."""
    repo = tmp_path / "kb"
    repo.mkdir()
    _git(["git", "init", "-q", "--initial-branch=main"], repo)
    _git(["git", "config", "user.email", "test@test"], repo)
    _git(["git", "config", "user.name", "test"], repo)
    (repo / "README.md").write_text("seed\n")
    _git(["git", "add", "."], repo)
    _git(["git", "commit", "-q", "-m", "seed"], repo)
    return repo


def test_push_to_draft_branch_creates_branch_and_commits(kb_repo: Path):
    target = kb_repo / "30_adr" / "test-slug" / "ADR-001-foo.md"
    target.parent.mkdir(parents=True)
    target.write_text("# ADR-001\n")

    result = push_to_draft_branch(
        kb_repo, "test-slug", [target], push_remote=False, today="2026-05-10",
    )

    assert result.ok
    assert result.branch == "draft/skill-v2-bootstrap-test-slug-2026-05-10"
    assert result.commit_sha is not None
    assert result.push_ok is False  # push_remote=False

    current = _git(["git", "rev-parse", "--abbrev-ref", "HEAD"], kb_repo).stdout.strip()
    assert current == "main"

    branches = _git(["git", "branch", "--list"], kb_repo).stdout
    assert "draft/skill-v2-bootstrap-test-slug-2026-05-10" in branches


def test_push_to_draft_branch_idempotent_no_changes(kb_repo: Path):
    target = kb_repo / "20_architecture" / "x" / "system.md"
    target.parent.mkdir(parents=True)
    target.write_text("# arch\n")

    r1 = push_to_draft_branch(
        kb_repo, "x", [target], push_remote=False, today="2026-05-10",
    )
    assert r1.ok

    r2 = push_to_draft_branch(
        kb_repo, "x", [target], push_remote=False, today="2026-05-10",
    )
    assert r2.ok
    assert r2.branch == r1.branch
    assert r2.commit_sha == r1.commit_sha


def test_push_to_draft_branch_not_a_repo(tmp_path: Path):
    not_repo = tmp_path / "norepo"
    not_repo.mkdir()
    result = push_to_draft_branch(not_repo, "x", [], push_remote=False)
    assert result.ok is False
    assert "not a git repo" in (result.error or "")


def test_push_to_draft_branch_restores_original_branch_on_error(kb_repo: Path):
    bogus = kb_repo / "nonexistent.md"
    result = push_to_draft_branch(
        kb_repo, "x", [bogus], push_remote=False, today="2026-05-10",
    )
    current = _git(["git", "rev-parse", "--abbrev-ref", "HEAD"], kb_repo).stdout.strip()
    assert current == "main"
