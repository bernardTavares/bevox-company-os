"""Tests for greenfield/generators/release_notes.py."""
import subprocess
from pathlib import Path

import pytest

from lib.knowledge_watcher.greenfield import SourceSignals, Tier
from lib.knowledge_watcher.greenfield.generators.release_notes import (
    generate_release_notes,
)


def _signals(repo_root, tags) -> SourceSignals:
    return SourceSignals(
        slug="myproj", repo_root=repo_root,
        has_schema_prisma=False, schema_models=[],
        package_json={}, deps={}, main_services=[], env_vars=[],
        has_readme=False, readme_text="",
        has_claude_md=False, claude_md_text="",
        git_tags=tags, services_count=0,
        has_auth_middleware=False, has_org_id_pattern=False,
    )


def _make_repo_with_tags(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    # Commits before tag v0.1.0
    for msg in ["feat: initial", "fix: typo"]:
        (repo / f"{msg.split(':')[0]}-{len(list(repo.glob('*.txt')))}.txt").write_text(msg)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "tag", "v0.1.0"], cwd=repo, check=True)
    # Commits between v0.1.0 and v1.0.0
    for msg in ["feat: add A", "refactor: cleanup", "fix: B", "chore: deps", "BREAKING: drop X"]:
        (repo / f"f-{len(list(repo.glob('*.txt')))}.txt").write_text(msg)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "tag", "v1.0.0"], cwd=repo, check=True)
    return repo


def test_no_tags_returns_empty(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sig = _signals(repo, [])
    assert generate_release_notes(sig) == []


def test_single_tag_creates_one_release(tmp_path):
    repo = _make_repo_with_tags(tmp_path)
    # signals.git_tags is sorted desc per spec; provide v0.1.0 only
    sig = _signals(repo, ["v0.1.0"])
    results = generate_release_notes(sig)
    assert len(results) == 1
    r = results[0]
    assert r.tier == Tier.MECANICO
    assert r.doc_type == "release-note"
    assert r.relative_path == "50_releases/myproj/0.1.0.md"
    assert r.cost_usd == 0.0
    body = r.content
    assert "Release 0.1.0" in body
    assert "tag: v0.1.0" in body
    assert "feat: initial" in body
    assert "fix: typo" in body


def test_two_tags_groups_commits_by_prefix(tmp_path):
    repo = _make_repo_with_tags(tmp_path)
    # tags desc (signals format)
    sig = _signals(repo, ["v1.0.0", "v0.1.0"])
    results = generate_release_notes(sig)
    assert len(results) == 2
    # first result is the chronologically older one (v0.1.0 contains initial commits)
    assert "0.1.0.md" in results[0].relative_path
    assert "1.0.0.md" in results[1].relative_path
    v100 = results[1].content
    assert "## Features" in v100
    assert "feat: add A" in v100
    assert "## Fixes" in v100
    assert "fix: B" in v100
    assert "## Refactors" in v100
    assert "refactor: cleanup" in v100
    assert "## Breaking changes" in v100
    assert "BREAKING: drop X" in v100
    assert "## Misc" in v100
    assert "chore: deps" in v100


def test_invalid_repo_returns_results_with_warnings(tmp_path):
    repo = tmp_path / "notarepo"
    repo.mkdir()
    sig = _signals(repo, ["v0.1.0"])
    results = generate_release_notes(sig)
    assert len(results) == 1
    # git log will fail on non-repo; we still create a doc (with empty content sections)
    body = results[0].content
    assert "Release 0.1.0" in body
    assert "no notable commits" in body or "not available" in body


def test_non_semver_tag_keeps_name(tmp_path):
    repo = _make_repo_with_tags(tmp_path)
    sig = _signals(repo, ["release-2026-Q1"])
    results = generate_release_notes(sig)
    # tag doesn't match v\d+\.\d+; keep as-is
    assert results[0].relative_path == "50_releases/myproj/release-2026-Q1.md"
