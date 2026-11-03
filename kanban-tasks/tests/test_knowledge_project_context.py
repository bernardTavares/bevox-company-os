"""Tests for lib/knowledge_watcher/project_context.py."""
import tempfile
import subprocess
from pathlib import Path

import pytest

from lib.knowledge_watcher.project_context import (
    detect_project_context,
    _git_age_months,
    _git_commit_count,
    _git_commits_last_n_days,
    _git_has_tags,
    _detect_has_schema_prisma,
    _detect_service_count,
)


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a temp git repo with 1 commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    (repo / "README.md").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "init"],
        cwd=repo, check=True,
    )
    return repo


def test_git_age_months_missing_repo_returns_zero(tmp_path):
    fake = tmp_path / "notarepo"
    fake.mkdir()
    assert _git_age_months(fake) == 0


def test_git_age_months_fresh_repo_returns_zero(tmp_git_repo):
    """Just-created repo → 0 months age."""
    assert _git_age_months(tmp_git_repo) == 0


def test_git_commit_count(tmp_git_repo):
    """Single commit → count 1."""
    assert _git_commit_count(tmp_git_repo) == 1


def test_git_commit_count_missing_repo_zero(tmp_path):
    fake = tmp_path / "notarepo"
    fake.mkdir()
    assert _git_commit_count(fake) == 0


def test_git_commits_last_30d(tmp_git_repo):
    """Just-created commit is within 30d."""
    assert _git_commits_last_n_days(tmp_git_repo, 30) == 1


def test_git_has_tags_false_by_default(tmp_git_repo):
    assert _git_has_tags(tmp_git_repo) is False


def test_git_has_tags_true_when_tagged(tmp_git_repo):
    subprocess.run(["git", "tag", "v1.0.0"], cwd=tmp_git_repo, check=True)
    assert _git_has_tags(tmp_git_repo) is True


def test_detect_has_schema_prisma_false(tmp_git_repo):
    assert _detect_has_schema_prisma(tmp_git_repo) is False


def test_detect_has_schema_prisma_true(tmp_git_repo):
    prisma = tmp_git_repo / "apps" / "api" / "prisma"
    prisma.mkdir(parents=True)
    (prisma / "schema.prisma").write_text("// schema")
    assert _detect_has_schema_prisma(tmp_git_repo) is True


def test_detect_service_count_apps_subdirs(tmp_git_repo):
    """service_count counts subdirs in apps/ and packages/."""
    (tmp_git_repo / "apps" / "api").mkdir(parents=True)
    (tmp_git_repo / "apps" / "web").mkdir(parents=True)
    (tmp_git_repo / "apps" / "worker").mkdir(parents=True)
    assert _detect_service_count(tmp_git_repo) == 3


def test_detect_service_count_no_apps_zero(tmp_git_repo):
    assert _detect_service_count(tmp_git_repo) == 0


def test_detect_project_context_full(tmp_git_repo):
    """Integration: detect_project_context returns dict with all signals."""
    meta_entry = {
        "source": "adopted",
        "has_customers": True,
        "has_metrics": False,
    }
    ctx = detect_project_context(tmp_git_repo, meta_entry)

    assert ctx["is_adopted"] is True
    assert ctx["age_months"] == 0
    assert ctx["commit_count"] == 1
    assert ctx["commits_last_30d"] == 1
    assert ctx["has_git_tags"] is False
    assert ctx["has_schema_prisma"] is False
    assert ctx["service_count"] == 0
    assert ctx["has_customers_flag"] is True
    assert ctx["has_metrics_flag"] is False


def test_detect_project_context_repo_missing(tmp_path):
    """Missing repo dir → ctx with zeros + is_adopted=False."""
    fake = tmp_path / "notarepo"
    meta_entry = {}
    ctx = detect_project_context(fake, meta_entry)
    assert ctx["age_months"] == 0
    assert ctx["commit_count"] == 0
