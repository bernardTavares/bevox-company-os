"""Tests for retirement/lifecycle.py — Categoria D."""
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.knowledge_watcher.retirement import RetirementCategory
from lib.knowledge_watcher.retirement.lifecycle import (
    detect_lifecycle,
    _get_file_last_commit_age_days,
)


def test_no_status_done_returns_empty(tmp_path):
    """No `Status: Done` → no signal regardless of age."""
    p = tmp_path / "doc.md"
    p.write_text("# Doc\n\nBody.")
    with patch.object(
        Path, 'is_file', return_value=True,
    ):
        signals = detect_lifecycle(p)
    assert signals == []


def test_status_done_with_recent_commit_no_signal(tmp_path):
    """Status: Done but recent commit → no signal."""
    p = tmp_path / "doc.md"
    p.write_text("---\nstatus: Done\n---\n# Doc")
    # Mock age to 5 days (below threshold 90)
    with patch(
        "lib.knowledge_watcher.retirement.lifecycle._get_file_last_commit_age_days",
        return_value=5,
    ):
        signals = detect_lifecycle(p)
    assert signals == []


def test_status_done_with_old_commit_flags(tmp_path):
    """Status: Done + commit > 90d → flag Cat D."""
    p = tmp_path / "doc.md"
    p.write_text("---\nstatus: Done\n---\n# Doc")
    with patch(
        "lib.knowledge_watcher.retirement.lifecycle._get_file_last_commit_age_days",
        return_value=120,
    ):
        signals = detect_lifecycle(p)
    assert len(signals) == 1
    assert signals[0].category == RetirementCategory.D_LIFECYCLE


def test_status_completed_pt_with_old_commit(tmp_path):
    p = tmp_path / "doc.md"
    p.write_text("---\nstatus: Concluída\n---\n# Doc")
    with patch(
        "lib.knowledge_watcher.retirement.lifecycle._get_file_last_commit_age_days",
        return_value=200,
    ):
        signals = detect_lifecycle(p)
    assert len(signals) == 1


def test_age_unknown_returns_empty(tmp_path):
    """If git fails (returns None), don't flag."""
    p = tmp_path / "doc.md"
    p.write_text("---\nstatus: Done\n---\n# Doc")
    with patch(
        "lib.knowledge_watcher.retirement.lifecycle._get_file_last_commit_age_days",
        return_value=None,
    ):
        signals = detect_lifecycle(p)
    assert signals == []


def test_missing_file_returns_empty(tmp_path):
    fake = tmp_path / "nope.md"
    assert detect_lifecycle(fake) == []
