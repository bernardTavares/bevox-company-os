"""Tests for knowledge_watcher.commands — 7 handlers."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from lib.knowledge_watcher.commands import CommandResult, EXIT_OK, EXIT_NOT_FOUND
from lib.knowledge_watcher.gap_registry import (
    GapRecord, GapStatus, GapSource, add_gap,
)
from lib.knowledge_watcher.state import default_state


def _seed_open_gap(state, gid="bevox-direct-aaa-spec", source=GapSource.F1):
    g = GapRecord(
        gap_id=gid, repo="bevox-direct", source=source,
        status=GapStatus.OPEN, doc_type="spec",
        commit_sha="aaaaaaa1234", path="00_inbox/bevox-direct/foo.md",
        draft_branch="draft/auto/2026-05-09-aaa-spec",
        created_at=datetime(2026, 5, 9, tzinfo=timezone.utc),
        snooze_until=None,
    )
    add_gap(state, g)
    return g


def test_command_result_shape():
    r = CommandResult(ok=True, reply="hi", exit_code=EXIT_OK)
    assert r.ok and r.reply == "hi" and r.exit_code == EXIT_OK


# ---------------------------------------------------------------------------
# P2.T2.2 — cmd_review
# ---------------------------------------------------------------------------

from lib.knowledge_watcher.commands import cmd_review


def test_cmd_review_returns_url():
    state = default_state()
    g = _seed_open_gap(state)
    r = cmd_review(state, g.gap_id, kb_remote_url="https://github.com/Bevox/bevox-knowledge")
    assert r.ok
    assert "https://github.com/Bevox/bevox-knowledge/tree/draft/auto/2026-05-09-aaa-spec" in r.reply


def test_cmd_review_unknown_id():
    state = default_state()
    r = cmd_review(state, "nonexistent", kb_remote_url="https://github.com/x/y")
    assert not r.ok
    assert r.exit_code == EXIT_NOT_FOUND
    assert "não encontrada" in r.reply.lower() or "not found" in r.reply.lower()


def test_cmd_review_f4_no_branch_returns_path_url():
    """F4 gaps don't have draft_branch — review returns blob URL on main."""
    from lib.knowledge_watcher.gap_registry import GapSource
    state = default_state()
    g = _seed_open_gap(state, gid="bevox-direct-r-3f8a2b", source=GapSource.F4)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["path"] = "30_adr/bevox-direct/ADR-001.md"
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["draft_branch"] = None
    r = cmd_review(state, g.gap_id, kb_remote_url="https://github.com/Bevox/bevox-knowledge")
    assert r.ok
    assert "blob/main/30_adr/bevox-direct/ADR-001.md" in r.reply


# ---------------------------------------------------------------------------
# P2.T2.3 — cmd_dismiss
# ---------------------------------------------------------------------------

from lib.knowledge_watcher.commands import cmd_dismiss


def test_cmd_dismiss_marks_gap_dismissed():
    state = default_state()
    g = _seed_open_gap(state)
    r = cmd_dismiss(state, g.gap_id)
    assert r.ok and r.exit_code == EXIT_OK
    assert "dismissed" in r.reply.lower()
    from lib.knowledge_watcher.gap_registry import get_gap
    assert get_gap(state, g.gap_id).status is GapStatus.DISMISSED


def test_cmd_dismiss_idempotent():
    state = default_state()
    g = _seed_open_gap(state)
    cmd_dismiss(state, g.gap_id)
    r = cmd_dismiss(state, g.gap_id)
    assert r.ok
    assert "já dismissed" in r.reply.lower() or "already dismissed" in r.reply.lower()


def test_cmd_dismiss_blocks_after_accepted():
    state = default_state()
    g = _seed_open_gap(state)
    from lib.knowledge_watcher.gap_registry import update_gap
    update_gap(state, g.gap_id, status=GapStatus.ACCEPTED)
    r = cmd_dismiss(state, g.gap_id)
    assert not r.ok
    from lib.knowledge_watcher.commands import EXIT_TERMINAL_LOCK
    assert r.exit_code == EXIT_TERMINAL_LOCK
    assert "accepted" in r.reply.lower()


def test_cmd_dismiss_unknown_id():
    state = default_state()
    r = cmd_dismiss(state, "nonexistent")
    assert not r.ok
    assert r.exit_code == EXIT_NOT_FOUND


# ---------------------------------------------------------------------------
# P2.T2.4 — cmd_postpone
# ---------------------------------------------------------------------------

from lib.knowledge_watcher.commands import cmd_postpone


def test_cmd_postpone_sets_snooze_until():
    state = default_state()
    g = _seed_open_gap(state)
    r = cmd_postpone(state, g.gap_id, days=7)
    assert r.ok
    from lib.knowledge_watcher.gap_registry import get_gap
    fetched = get_gap(state, g.gap_id)
    assert fetched.status is GapStatus.SNOOZED
    assert fetched.snooze_until is not None
    delta = fetched.snooze_until - datetime.now(timezone.utc)
    # Use total_seconds to avoid timedelta.days floor truncation
    assert 6.5 * 86400 < delta.total_seconds() < 7.5 * 86400


def test_cmd_postpone_replaces_not_cumulative():
    state = default_state()
    g = _seed_open_gap(state)
    cmd_postpone(state, g.gap_id, days=3)
    r = cmd_postpone(state, g.gap_id, days=14)
    assert r.ok
    from lib.knowledge_watcher.gap_registry import get_gap
    fetched = get_gap(state, g.gap_id)
    delta = fetched.snooze_until - datetime.now(timezone.utc)
    # 14 days total, not 3+14=17; use total_seconds to avoid floor truncation
    assert 13 * 86400 < delta.total_seconds() < 15 * 86400


def test_cmd_postpone_invalid_days():
    state = default_state()
    g = _seed_open_gap(state)
    r = cmd_postpone(state, g.gap_id, days=0)
    assert not r.ok
    r2 = cmd_postpone(state, g.gap_id, days=-5)
    assert not r2.ok
    r3 = cmd_postpone(state, g.gap_id, days=400)
    assert not r3.ok


# ---------------------------------------------------------------------------
# P2.T2.5 — cmd_keep + cmd_keep_permanent
# ---------------------------------------------------------------------------

from lib.knowledge_watcher.commands import cmd_keep, cmd_keep_permanent


def test_cmd_keep_snoozes_90_days():
    state = default_state()
    g = _seed_open_gap(state, gid="bevox-direct-r-aaa", source=GapSource.F4)
    r = cmd_keep(state, g.gap_id)
    assert r.ok
    from lib.knowledge_watcher.gap_registry import get_gap
    fetched = get_gap(state, g.gap_id)
    delta = fetched.snooze_until - datetime.now(timezone.utc)
    assert 89 < delta.total_seconds() / 86400 < 91


def test_cmd_keep_only_for_f4():
    """/keep is a F4-retirement-specific command. F1 gaps → use /postpone."""
    state = default_state()
    g = _seed_open_gap(state, source=GapSource.F1)
    r = cmd_keep(state, g.gap_id)
    assert not r.ok
    assert "f4" in r.reply.lower() or "retirement" in r.reply.lower()


def test_cmd_keep_unknown_id():
    state = default_state()
    from lib.knowledge_watcher.commands import EXIT_NOT_FOUND
    r = cmd_keep(state, "nonexistent")
    assert not r.ok
    assert r.exit_code == EXIT_NOT_FOUND


def test_cmd_keep_permanent_inserts_html_comment(tmp_path):
    """W3.5: keep-permanent edits doc inserting HTML comment + commits draft branch."""
    import subprocess
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@x"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=kb, check=True, capture_output=True)
    doc_path = kb / "30_adr" / "bevox-direct" / "ADR-001.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("# ADR-001\n\nbody.\n")
    subprocess.run(["git", "add", "."], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=kb, check=True, capture_output=True)

    state = default_state()
    g = _seed_open_gap(state, gid="bevox-direct-r-3f8a2b", source=GapSource.F4)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["path"] = "30_adr/bevox-direct/ADR-001.md"
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["draft_branch"] = None

    r = cmd_keep_permanent(state, g.gap_id, kb_dir=kb, dry_run=False, push=False)
    assert r.ok
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=kb,
        capture_output=True, text=True,
    ).stdout
    assert "draft/keep-permanent" in branches
    # Marker lives in the draft branch, not in main working tree
    # (commit_in_draft_branch restores original branch after commit)
    branch = f"draft/keep-permanent/{g.gap_id}"
    git_show = subprocess.run(
        ["git", "show", f"{branch}:30_adr/bevox-direct/ADR-001.md"],
        cwd=kb, capture_output=True, text=True,
    )
    assert git_show.returncode == 0
    assert "<!-- knowledge-watcher: do-not-retire -->" in git_show.stdout


def test_cmd_keep_permanent_idempotent_marker_already_present(tmp_path):
    """Doc already with marker → noop, no commit."""
    import subprocess
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@x"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=kb, check=True, capture_output=True)
    doc_path = kb / "30_adr" / "bevox-direct" / "ADR-001.md"
    doc_path.parent.mkdir(parents=True)
    doc_path.write_text("# ADR-001\n\nbody.\n\n<!-- knowledge-watcher: do-not-retire -->\n")
    subprocess.run(["git", "add", "."], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=kb, check=True, capture_output=True)

    state = default_state()
    g = _seed_open_gap(state, gid="bevox-direct-r-bbb", source=GapSource.F4)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["path"] = "30_adr/bevox-direct/ADR-001.md"

    r = cmd_keep_permanent(state, g.gap_id, kb_dir=kb, dry_run=False, push=False)
    assert r.ok
    assert "noop" in r.reply.lower() or "já tem" in r.reply.lower()


# ---------------------------------------------------------------------------
# P2.T2.6 — cmd_retire
# ---------------------------------------------------------------------------

from lib.knowledge_watcher.commands import cmd_retire


def test_cmd_retire_moves_doc_to_retired(tmp_path):
    import subprocess
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@x"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=kb, check=True, capture_output=True)
    src = kb / "30_adr" / "bevox-direct" / "ADR-001.md"
    src.parent.mkdir(parents=True)
    src.write_text("# ADR-001\n")
    subprocess.run(["git", "add", "."], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=kb, check=True, capture_output=True)

    state = default_state()
    g = _seed_open_gap(state, gid="bevox-direct-r-aaa", source=GapSource.F4)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["path"] = "30_adr/bevox-direct/ADR-001.md"

    r = cmd_retire(state, g.gap_id, kb_dir=kb, push=False)
    assert r.ok
    # Original src on main untouched
    assert src.is_file()
    # Draft branch was created
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=kb,
        capture_output=True, text=True,
    ).stdout
    branch_name = f"draft/auto/retire-{g.gap_id}"
    assert branch_name in branches
    from lib.knowledge_watcher.gap_registry import get_gap
    assert get_gap(state, g.gap_id).status is GapStatus.RETIRED


def test_cmd_retire_only_for_f4():
    state = default_state()
    g = _seed_open_gap(state, source=GapSource.F1)
    r = cmd_retire(state, g.gap_id, kb_dir=Path("/tmp"), push=False)
    assert not r.ok


def test_cmd_retire_idempotent_on_retired():
    state = default_state()
    g = _seed_open_gap(state, gid="bevox-direct-r-bbb2", source=GapSource.F4)
    from lib.knowledge_watcher.gap_registry import update_gap
    update_gap(state, g.gap_id, status=GapStatus.RETIRED)
    r = cmd_retire(state, g.gap_id, kb_dir=Path("/tmp"), push=False)
    assert r.ok  # noop
    assert "já retired" in r.reply.lower() or "already retired" in r.reply.lower()


def test_cmd_retire_unknown_id():
    state = default_state()
    from lib.knowledge_watcher.commands import EXIT_NOT_FOUND
    r = cmd_retire(state, "nonexistent-gap", kb_dir=Path("/tmp"), push=False)
    assert not r.ok
    assert r.exit_code == EXIT_NOT_FOUND


# ---------------------------------------------------------------------------
# P2.T2.7 — cmd_accept
# ---------------------------------------------------------------------------

from lib.knowledge_watcher.commands import cmd_accept


def test_cmd_accept_step1_returns_token():
    state = default_state()
    g = _seed_open_gap(state)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["doc_type"] = "release-note"
    r = cmd_accept(state, g.gap_id, confirm_token=None, kb_dir=Path("/tmp"), push=False)
    assert r.ok
    assert "60s" in r.reply
    assert "_pending_accept" in state
    assert g.gap_id in state["_pending_accept"]


def test_cmd_accept_step2_with_invalid_token_fails():
    from lib.knowledge_watcher.commands import EXIT_INVALID_TOKEN
    state = default_state()
    g = _seed_open_gap(state)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["doc_type"] = "release-note"
    cmd_accept(state, g.gap_id, confirm_token=None, kb_dir=Path("/tmp"), push=False)
    r = cmd_accept(state, g.gap_id, confirm_token="WRONG-TOKEN", kb_dir=Path("/tmp"), push=False)
    assert not r.ok
    assert r.exit_code == EXIT_INVALID_TOKEN


def test_cmd_accept_step2_with_expired_token():
    """Token gerado >60s atrás é inválido."""
    state = default_state()
    g = _seed_open_gap(state)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["doc_type"] = "release-note"
    cmd_accept(state, g.gap_id, confirm_token=None, kb_dir=Path("/tmp"), push=False)
    pending = state["_pending_accept"][g.gap_id]
    # Backdate token creation
    state["_pending_accept"][g.gap_id]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=120)
    ).isoformat().replace("+00:00", "Z")
    r = cmd_accept(
        state, g.gap_id, confirm_token=pending["token"],
        kb_dir=Path("/tmp"), push=False,
    )
    assert not r.ok
    assert "expirado" in r.reply.lower() or "expired" in r.reply.lower()


def test_cmd_accept_full_flow_ff_merge(tmp_path):
    """Step 1 → Step 2 with valid token → FF-merge draft → main."""
    import subprocess
    kb = tmp_path / "kb"
    kb.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@x"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=kb, check=True, capture_output=True)
    (kb / "README.md").write_text("# kb\n")
    subprocess.run(["git", "add", "."], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", "draft/auto/release"], cwd=kb, check=True, capture_output=True)
    (kb / "50_releases" / "bevox-direct").mkdir(parents=True)
    (kb / "50_releases" / "bevox-direct" / "v1.0.md").write_text("# v1.0\n")
    subprocess.run(["git", "add", "."], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "release"], cwd=kb, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "main"], cwd=kb, check=True, capture_output=True)

    state = default_state()
    g = _seed_open_gap(state)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["doc_type"] = "release-note"
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["draft_branch"] = "draft/auto/release"

    r1 = cmd_accept(state, g.gap_id, confirm_token=None, kb_dir=kb, push=False)
    assert r1.ok
    token = state["_pending_accept"][g.gap_id]["token"]

    r2 = cmd_accept(state, g.gap_id, confirm_token=token, kb_dir=kb, push=False)
    assert r2.ok
    log = subprocess.run(
        ["git", "log", "--oneline", "main"], cwd=kb,
        capture_output=True, text=True,
    ).stdout
    assert "release" in log
    from lib.knowledge_watcher.gap_registry import get_gap
    assert get_gap(state, g.gap_id).status is GapStatus.ACCEPTED
    assert g.gap_id not in state.get("_pending_accept", {})


def test_cmd_accept_only_release_note():
    state = default_state()
    g = _seed_open_gap(state)  # doc_type=spec by default
    r = cmd_accept(state, g.gap_id, confirm_token=None, kb_dir=Path("/tmp"), push=False)
    assert not r.ok
    assert "release-note" in r.reply


def test_cmd_accept_already_accepted_noop():
    state = default_state()
    g = _seed_open_gap(state)
    state["repos"]["bevox-direct"]["gaps"][g.gap_id]["doc_type"] = "release-note"
    from lib.knowledge_watcher.gap_registry import update_gap
    update_gap(state, g.gap_id, status=GapStatus.ACCEPTED)
    r = cmd_accept(state, g.gap_id, confirm_token=None, kb_dir=Path("/tmp"), push=False)
    assert r.ok
    assert "já accepted" in r.reply.lower() or "already accepted" in r.reply.lower()
