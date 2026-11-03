"""Tests for commit_watcher/workflow.py."""
import subprocess
from pathlib import Path

from lib.knowledge_watcher.commit_watcher import (
    Strategy,
)
from lib.knowledge_watcher.commit_watcher.workflow import process_repo_commits
from lib.knowledge_watcher.gap_registry import get_gap, GapStatus
from lib.knowledge_watcher.state import default_state


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    return repo


def _commit(repo: Path, msg: str, files: dict[str, str] | None = None) -> str:
    files = files or {"f.txt": msg}
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", msg], cwd=repo, check=True, capture_output=True)
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def test_process_no_commits_returns_empty(tmp_path):
    repo = _make_repo(tmp_path)
    kb = tmp_path / "kb"; kb.mkdir()
    state = tmp_path / "s.json"
    gaps, last = process_repo_commits(
        slug="p", repo_root=repo, kb_root=kb, state_path=state,
    )
    assert gaps == []
    assert last is None


def test_process_classifies_and_dispatches_strategies(tmp_path):
    repo = _make_repo(tmp_path)
    sha = _commit(
        repo, "feat: add template service",
        files={"apps/api/src/services/template.service.ts": "x"},
    )
    kb = tmp_path / "kb"; kb.mkdir()
    state = tmp_path / "s.json"

    gaps, last = process_repo_commits(
        slug="p", repo_root=repo, kb_root=kb, state_path=state,
    )
    assert last == sha
    assert len(gaps) == 1
    assert gaps[0].strategy == Strategy.DRAFT_SKELETON  # spec
    # _gaps.md created
    gaps_md = kb / "00_inbox" / "p" / "_gaps.md"
    assert gaps_md.exists()
    content = gaps_md.read_text()
    assert "Documentation gaps — p" in content
    assert "[" + sha[:7] + "]" in content


def test_process_skips_none_classified_commits(tmp_path):
    repo = _make_repo(tmp_path)
    sha = _commit(repo, "test: only tests", files={"a.test.ts": "x"})
    kb = tmp_path / "kb"; kb.mkdir()
    state = tmp_path / "s.json"

    gaps, last = process_repo_commits(
        slug="p", repo_root=repo, kb_root=kb, state_path=state,
    )
    assert gaps == []
    assert last == sha  # advanced even for NONE
    # No _gaps.md created (no entries written)
    assert not (kb / "00_inbox" / "p" / "_gaps.md").exists()


def test_process_dry_run_does_not_write_gaps_md(tmp_path):
    repo = _make_repo(tmp_path)
    _commit(
        repo, "feat: add template service",
        files={"apps/api/src/services/template.service.ts": "x"},
    )
    kb = tmp_path / "kb"; kb.mkdir()
    state = tmp_path / "s.json"

    gaps, _ = process_repo_commits(
        slug="p", repo_root=repo, kb_root=kb, state_path=state,
        dry_run=True,
    )
    assert len(gaps) == 1
    # In dry_run, no _gaps.md should be written
    assert not (kb / "00_inbox" / "p" / "_gaps.md").exists()
    # In dry_run, no draft skeleton/release/adr file should be written either
    inbox_dir = kb / "00_inbox" / "p"
    if inbox_dir.exists():
        assert list(inbox_dir.glob("*-spec-draft.md")) == []
        assert list(inbox_dir.glob("*-adr-template.md")) == []
    assert not (kb / "50_releases").exists()


def test_process_advances_last_sha_through_multiple_commits(tmp_path):
    repo = _make_repo(tmp_path)
    sha1 = _commit(repo, "feat: A", files={"apps/api/src/services/a.service.ts": "1"})
    sha2 = _commit(repo, "test: B", files={"a.test.ts": "2"})  # NONE — skipped
    sha3 = _commit(repo, "feat: C", files={"apps/api/src/services/c.service.ts": "3"})
    kb = tmp_path / "kb"; kb.mkdir()
    state = tmp_path / "s.json"

    gaps, last = process_repo_commits(
        slug="p", repo_root=repo, kb_root=kb, state_path=state,
    )
    assert last == sha3  # advanced through all
    assert len(gaps) == 2  # sha1 + sha3 (sha2 skipped)


def test_workflow_gap_id_property(tmp_path):
    """W3.5: GapDraft.gap_id is a deterministic property derived from slug+sha+doctype."""
    repo = _make_repo(tmp_path)
    sha = _commit(
        repo, "feat: add template service",
        files={"apps/api/src/services/template.service.ts": "x"},
    )
    kb = tmp_path / "kb"; kb.mkdir()
    state_path = tmp_path / "s.json"

    gaps, _ = process_repo_commits(
        slug="bevox-direct", repo_root=repo, kb_root=kb, state_path=state_path,
    )
    assert len(gaps) >= 1
    g = gaps[0]
    # gap_id format: <repo>-<short7>-<doctype>
    assert g.gap_id == f"bevox-direct-{sha[:7]}-{g.classifier_result.doc_type.value}"
    # deterministic: calling again returns same value
    assert g.gap_id == g.gap_id


def test_workflow_registers_gap_in_state(tmp_path):
    """W3.5: process_repo_commits registers gap in state via gap_registry."""
    repo = _make_repo(tmp_path)
    _commit(
        repo, "feat: add template service",
        files={"apps/api/src/services/template.service.ts": "x"},
    )
    kb = tmp_path / "kb"; kb.mkdir()
    state_path = tmp_path / "s.json"
    state = default_state()

    gaps, _ = process_repo_commits(
        slug="bevox-direct", repo_root=repo, kb_root=kb,
        state_path=state_path, state=state, since_sha=None,
        dry_run=False, backfill_limit=50,
    )
    assert len(gaps) >= 1
    g = gaps[0]
    assert g.gap_id  # property works

    fetched = get_gap(state, g.gap_id)
    assert fetched is not None
    assert fetched.status is GapStatus.OPEN
    assert fetched.repo == "bevox-direct"


def test_workflow_dry_run_does_not_register_gap_in_state(tmp_path):
    """W3.5: dry_run skips gap registration in state even when state is passed."""
    repo = _make_repo(tmp_path)
    _commit(
        repo, "feat: add template service",
        files={"apps/api/src/services/template.service.ts": "x"},
    )
    kb = tmp_path / "kb"; kb.mkdir()
    state_path = tmp_path / "s.json"
    state = default_state()

    gaps, _ = process_repo_commits(
        slug="bevox-direct", repo_root=repo, kb_root=kb,
        state_path=state_path, state=state, since_sha=None,
        dry_run=True, backfill_limit=50,
    )
    assert len(gaps) >= 1
    g = gaps[0]
    # state must remain empty — no gaps registered during dry_run
    fetched = get_gap(state, g.gap_id)
    assert fetched is None


def test_workflow_no_state_param_does_not_crash(tmp_path):
    """W3.5: omitting state param (None) is backward-compat; no registration."""
    repo = _make_repo(tmp_path)
    _commit(
        repo, "feat: add template service",
        files={"apps/api/src/services/template.service.ts": "x"},
    )
    kb = tmp_path / "kb"; kb.mkdir()
    state_path = tmp_path / "s.json"

    # No state= argument — backward compat
    gaps, last = process_repo_commits(
        slug="p", repo_root=repo, kb_root=kb, state_path=state_path,
    )
    assert len(gaps) >= 1
    assert last is not None


def test_workflow_gap_id_idempotent_in_state(tmp_path):
    """W3.5: calling add_gap twice with same gap_id is a no-op (idempotent)."""
    repo = _make_repo(tmp_path)
    _commit(
        repo, "feat: add template service",
        files={"apps/api/src/services/template.service.ts": "x"},
    )
    kb = tmp_path / "kb"; kb.mkdir()
    state_path = tmp_path / "s.json"
    state = default_state()

    # First run
    gaps1, _ = process_repo_commits(
        slug="bevox-direct", repo_root=repo, kb_root=kb,
        state_path=state_path, state=state, since_sha=None,
        dry_run=False, backfill_limit=50,
    )
    assert len(gaps1) >= 1
    gap_id = gaps1[0].gap_id

    # Verify registered
    fetched1 = get_gap(state, gap_id)
    assert fetched1 is not None

    # Second call with same since_sha=None re-processes same commits
    # but add_gap is idempotent — should not duplicate or crash
    state2 = default_state()
    from lib.knowledge_watcher.gap_registry import add_gap, GapRecord, GapStatus, GapSource
    from datetime import datetime, timezone
    existing = fetched1
    add_gap(state2, existing)
    add_gap(state2, existing)  # duplicate — no-op
    gaps_dict = state2["repos"]["bevox-direct"]["gaps"]
    assert len(gaps_dict) == 1
