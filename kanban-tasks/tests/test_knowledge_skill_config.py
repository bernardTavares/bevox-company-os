"""Tests for skill_config.py + scoring override read (W8.P6)."""
import json
from pathlib import Path

import pytest

from lib.knowledge_watcher.skill_config import (
    read_config, write_config, set_doc_type_threshold, get_doc_type_thresholds,
)


def _setup_path(tmp_path: Path, monkeypatch) -> Path:
    p = tmp_path / "skill_config.json"
    monkeypatch.setenv("OPENCLAW_KNOWLEDGE_SKILL_CONFIG", str(p))
    return p


def test_read_missing_file_returns_default(tmp_path, monkeypatch):
    _setup_path(tmp_path, monkeypatch)
    cfg = read_config()
    assert cfg["version"] == 1
    assert cfg["f4_overrides"] == {}


def test_set_doc_type_threshold_persists(tmp_path, monkeypatch):
    p = _setup_path(tmp_path, monkeypatch)
    set_doc_type_threshold("adr", 1.0)
    raw = json.loads(p.read_text())
    assert raw["f4_overrides"]["doc_type_thresholds"]["adr"] == 1.0


def test_set_doc_type_threshold_idempotent(tmp_path, monkeypatch):
    _setup_path(tmp_path, monkeypatch)
    set_doc_type_threshold("adr", 1.0)
    set_doc_type_threshold("adr", 1.0)
    set_doc_type_threshold("spec", 0.85)
    cfg = read_config()
    assert cfg["f4_overrides"]["doc_type_thresholds"] == {
        "adr": 1.0, "spec": 0.85,
    }


def test_get_doc_type_thresholds_returns_overrides(tmp_path, monkeypatch):
    _setup_path(tmp_path, monkeypatch)
    set_doc_type_threshold("adr", 0.95)
    assert get_doc_type_thresholds() == {"adr": 0.95}


def test_scoring_threshold_for_uses_override(tmp_path, monkeypatch):
    _setup_path(tmp_path, monkeypatch)
    from lib.knowledge_watcher.retirement.scoring import threshold_for
    # Default ADR = 0.9; override to 1.0
    assert threshold_for("adr") == 0.9
    set_doc_type_threshold("adr", 1.0)
    assert threshold_for("adr") == 1.0


def test_scoring_threshold_for_falls_back_to_default(tmp_path, monkeypatch):
    _setup_path(tmp_path, monkeypatch)
    from lib.knowledge_watcher.retirement.scoring import threshold_for
    assert threshold_for("spec") == 0.7  # default SCORE_THRESHOLD
    assert threshold_for("architecture") == 0.8  # hardcoded W7
    assert threshold_for(None) == 0.7
