"""Tests for lib/knowledge_watcher/commit_watcher/git_scan.py."""
import subprocess
from pathlib import Path

import pytest

from lib.knowledge_watcher.commit_watcher.git_scan import list_unprocessed_commits


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    return repo


def _commit(repo: Path, msg: str, file_name: str = "f.txt", content: str = "x") -> str:
    (repo / file_name).write_text(content)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def test_list_unprocessed_no_since_returns_recent_commits(tmp_path):
    repo = _make_repo(tmp_path)
    sha1 = _commit(repo, "feat: a")
    sha2 = _commit(repo, "feat: b", file_name="f2.txt")
    commits = list_unprocessed_commits(repo, since_sha=None, backfill_limit=10)
    assert len(commits) == 2
    assert commits[0].sha == sha1  # oldest first
    assert commits[1].sha == sha2


def test_list_unprocessed_since_excludes_known(tmp_path):
    repo = _make_repo(tmp_path)
    sha1 = _commit(repo, "feat: a")
    sha2 = _commit(repo, "feat: b", file_name="f2.txt")
    commits = list_unprocessed_commits(repo, since_sha=sha1, backfill_limit=10)
    assert len(commits) == 1
    assert commits[0].sha == sha2


def test_list_unprocessed_backfill_limit(tmp_path):
    repo = _make_repo(tmp_path)
    shas = [_commit(repo, f"feat: c{i}", file_name=f"f{i}.txt") for i in range(5)]
    commits = list_unprocessed_commits(repo, since_sha=None, backfill_limit=3)
    assert len(commits) == 3
    assert [c.sha for c in commits] == shas[-3:]


def test_list_unprocessed_skips_skip_knowledge(tmp_path):
    repo = _make_repo(tmp_path)
    _commit(repo, "feat: a")
    _commit(repo, "feat: b\n\n[skip-knowledge]", file_name="f2.txt")
    _commit(repo, "feat: c", file_name="f3.txt")
    commits = list_unprocessed_commits(repo, since_sha=None, backfill_limit=10, skip_marker=True)
    assert len(commits) == 2
    assert all("[skip-knowledge]" not in c.body for c in commits)


def test_list_unprocessed_invalid_repo(tmp_path):
    repo = tmp_path / "notarepo"
    repo.mkdir()
    commits = list_unprocessed_commits(repo, since_sha=None)
    assert commits == []
