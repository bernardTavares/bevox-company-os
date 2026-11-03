"""Tests for commit_watcher/runner.py."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.knowledge_watcher.commit_watcher.runner import run_audit


def _make_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True)
    p = path / "apps" / "api" / "src" / "services"
    p.mkdir(parents=True, exist_ok=True)
    (p / "x.service.ts").write_text("export const x=1;")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "feat: add x service"],
                   cwd=path, check=True, capture_output=True)
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _write_meta(meta_path: Path, projects: dict) -> None:
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps({"version": 1, "projects": projects}))


def test_run_audit_skips_opted_out(tmp_path, monkeypatch):
    meta_path = tmp_path / "meta.json"
    _write_meta(meta_path, {"p": {"knowledge_watcher": {"opt_in": False}}})
    state = tmp_path / "state.json"

    with patch("lib.knowledge_watcher.commit_watcher.runner._dispatch_to_telegram",
               return_value=True):
        results = run_audit(
            meta_path, tmp_path / "kb", tmp_path / "code",
            state_path=state, dry_run=True,
        )
    assert len(results) == 1
    assert results[0].skipped_reason == "knowledge_watcher.opt_in=false"


def test_run_audit_skips_missing_repo(tmp_path):
    meta_path = tmp_path / "meta.json"
    _write_meta(meta_path, {"p": {"knowledge_watcher": {"opt_in": True}}})
    state = tmp_path / "state.json"
    code = tmp_path / "code"
    code.mkdir()

    with patch("lib.knowledge_watcher.commit_watcher.runner._dispatch_to_telegram",
               return_value=True):
        results = run_audit(
            meta_path, tmp_path / "kb", code,
            state_path=state, dry_run=True,
        )
    assert len(results) == 1
    assert "repo missing" in results[0].skipped_reason


def test_run_audit_processes_repo_and_writes_state(tmp_path):
    meta_path = tmp_path / "meta.json"
    _write_meta(meta_path, {"p": {"knowledge_watcher": {"opt_in": True}}})
    code = tmp_path / "code"
    repo = code / "p"
    sha = _make_repo(repo)
    kb = tmp_path / "kb"
    kb.mkdir()
    state = tmp_path / "state.json"

    with patch("lib.knowledge_watcher.commit_watcher.runner._dispatch_to_telegram",
               return_value=True) as m_send:
        results = run_audit(
            meta_path, kb, code, state_path=state, dry_run=False,
        )
    assert len(results) == 1
    assert results[0].repo_slug == "p"
    assert results[0].last_commit_processed == sha
    # state.json now has last_commit_processed
    state_data = json.loads(state.read_text())
    assert state_data["repos"]["p"]["last_commit_processed"] == sha
    # last_run_at also stamped on this run (regression: was None before W7 fix)
    assert state_data["repos"]["p"]["last_run_at"] is not None
    assert state_data["repos"]["p"]["last_run_at"].endswith("Z")
    # global last_full_audit_at also stamped (regression: was None forever)
    assert state_data["global"]["last_full_audit_at"] is not None
    assert state_data["global"]["last_full_audit_at"].endswith("Z")
    # Telegram dispatched once
    m_send.assert_called()


def test_run_audit_stamps_last_run_at_even_when_no_new_commits(tmp_path):
    """Regression: last_run_at was only updated when last_sha was truthy.
    Re-running with same SHA must still bump last_run_at.
    """
    meta_path = tmp_path / "meta.json"
    _write_meta(meta_path, {"p": {"knowledge_watcher": {"opt_in": True}}})
    code = tmp_path / "code"
    repo = code / "p"
    sha = _make_repo(repo)
    kb = tmp_path / "kb"
    kb.mkdir()
    state = tmp_path / "state.json"

    # Pre-populate state with last_commit_processed = current sha so the
    # second run has no new commits to process.
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({
        "version": 2,
        "repos": {"p": {
            "last_commit_processed": sha,
            "last_run_at": None,
            "gaps_open": 0,
            "gaps_dismissed_total": 0,
            "retirement_keep_until": {},
            "gaps": {},
        }},
        "global": {"last_full_audit_at": None, "f1_telegram_digest_seq": 0},
    }))

    with patch("lib.knowledge_watcher.commit_watcher.runner._dispatch_to_telegram",
               return_value=True):
        run_audit(meta_path, kb, code, state_path=state, dry_run=False)

    state_data = json.loads(state.read_text())
    assert state_data["repos"]["p"]["last_run_at"] is not None
    assert state_data["repos"]["p"]["last_commit_processed"] == sha  # unchanged
    assert state_data["global"]["last_full_audit_at"] is not None


def test_run_audit_dry_run_no_state_write(tmp_path):
    meta_path = tmp_path / "meta.json"
    _write_meta(meta_path, {"p": {"knowledge_watcher": {"opt_in": True}}})
    code = tmp_path / "code"
    repo = code / "p"
    _make_repo(repo)
    kb = tmp_path / "kb"
    kb.mkdir()
    state = tmp_path / "state.json"

    with patch("lib.knowledge_watcher.commit_watcher.runner._dispatch_to_telegram",
               return_value=True) as m_send:
        run_audit(meta_path, kb, code, state_path=state, dry_run=True)
    assert not state.exists()
    m_send.assert_not_called()


def test_run_audit_filters_to_single_project(tmp_path):
    meta_path = tmp_path / "meta.json"
    _write_meta(meta_path, {
        "p1": {"knowledge_watcher": {"opt_in": True}},
        "p2": {"knowledge_watcher": {"opt_in": True}},
    })
    code = tmp_path / "code"
    _make_repo(code / "p1")
    _make_repo(code / "p2")
    kb = tmp_path / "kb"
    kb.mkdir()
    state = tmp_path / "state.json"

    with patch("lib.knowledge_watcher.commit_watcher.runner._dispatch_to_telegram",
               return_value=True):
        results = run_audit(
            meta_path, kb, code, state_path=state, dry_run=True,
            project="p1",
        )
    assert len(results) == 1
    assert results[0].repo_slug == "p1"


def test_run_audit_handles_workflow_exception_gracefully(tmp_path):
    """Bad/poison commit should not crash entire loop."""
    meta_path = tmp_path / "meta.json"
    _write_meta(meta_path, {"p": {"knowledge_watcher": {"opt_in": True}}})
    code = tmp_path / "code"
    _make_repo(code / "p")
    kb = tmp_path / "kb"; kb.mkdir()
    state = tmp_path / "state.json"

    with patch("lib.knowledge_watcher.commit_watcher.runner.process_repo_commits",
               side_effect=RuntimeError("classifier blew up")):
        with patch("lib.knowledge_watcher.commit_watcher.runner._dispatch_to_telegram",
                   return_value=True):
            results = run_audit(
                meta_path, kb, code, state_path=state, dry_run=False,
            )
    assert len(results) == 1
    assert "RuntimeError" in results[0].skipped_reason
