"""Tests for lib/knowledge_watcher/state.py."""
import json
from pathlib import Path

import pytest

from lib.knowledge_watcher import state as kw_state


def test_default_state_returns_skeleton():
    """default_state() returns expected schema."""
    s = kw_state.default_state()
    assert s["version"] == 2
    assert s["repos"] == {}
    assert "global" in s
    assert s["global"]["last_full_audit_at"] is None
    assert s["global"]["f1_telegram_digest_seq"] == 0


def test_read_state_creates_default_when_missing(tmp_path):
    """If state.json doesn't exist, read_state returns default."""
    path = tmp_path / "state.json"
    s = kw_state.read_state(path)
    assert s == kw_state.default_state()


def test_write_then_read_roundtrip(tmp_path):
    """write_state then read_state returns same data."""
    path = tmp_path / "state.json"
    s = kw_state.default_state()
    s["repos"]["bevox-direct"] = {
        "last_commit_processed": "abc1234",
        "last_run_at": "2026-05-08T14:30:00Z",
        "gaps_open": 5,
    }
    kw_state.write_state(path, s)

    loaded = kw_state.read_state(path)
    assert loaded["repos"]["bevox-direct"]["last_commit_processed"] == "abc1234"
    assert loaded["repos"]["bevox-direct"]["gaps_open"] == 5


def test_get_repo_state_returns_default_for_unknown(tmp_path):
    """get_repo_state returns empty repo state for unknown slug."""
    s = kw_state.default_state()
    repo = kw_state.get_repo_state(s, "unknown-slug")
    assert repo["last_commit_processed"] is None
    assert repo["gaps_open"] == 0


def test_set_repo_state_persists_fields(tmp_path):
    """set_repo_state merges fields into repo state."""
    s = kw_state.default_state()
    kw_state.set_repo_state(s, "bevox-direct", {
        "last_commit_processed": "def5678",
        "gaps_open": 3,
    })
    assert s["repos"]["bevox-direct"]["last_commit_processed"] == "def5678"
    assert s["repos"]["bevox-direct"]["gaps_open"] == 3


def test_write_creates_parent_directory(tmp_path):
    """write_state creates parent dir if missing."""
    nested = tmp_path / "deep" / "nested" / "state.json"
    s = kw_state.default_state()
    kw_state.write_state(nested, s)
    assert nested.exists()
    assert json.loads(nested.read_text())["version"] == 2


def test_default_repo_state_includes_gaps_map():
    """v2: cada repo state tem gaps: {} default."""
    rs = kw_state.default_repo_state()
    assert "gaps" in rs
    assert rs["gaps"] == {}


def test_default_state_schema_version_is_2():
    """v2: default_state() returns version 2."""
    assert kw_state.SCHEMA_VERSION == 2
    s = kw_state.default_state()
    assert s["version"] == 2


def test_read_state_migrates_v1_to_v2(tmp_path):
    """state.json v1 (sem 'gaps' field) lido como v2 default — não quebra."""
    p = tmp_path / "state.json"
    p.write_text(json.dumps({
        "version": 1,
        "repos": {"bevox-direct": {
            "last_commit_processed": "abc",
            "gaps_open": 0,
        }},
        "global": {"last_full_audit_at": None, "f1_telegram_digest_seq": 0},
    }))
    s = kw_state.read_state(p)
    # After migration, v1 state files treated as invalid version → return default v2
    assert s["version"] == 2
    assert s["repos"] == {}
