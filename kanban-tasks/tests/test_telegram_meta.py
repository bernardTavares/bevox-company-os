"""Tests for scripts/lib/telegram_meta.py."""
import json
import sys
from pathlib import Path

import pytest

# Add scripts/lib to path
LIB_DIR = Path(f"{Path.home()}/.openclaw/scripts/lib")
sys.path.insert(0, str(LIB_DIR))


def _write_meta(path: Path, slug: str, topics: dict | None) -> None:
    meta = {
        "version": 1,
        "projects": [
            {
                "id": slug,
                "telegram": {"chat_id": -100, "topics": topics or {}},
            }
        ],
    }
    path.write_text(json.dumps(meta))


def test_returns_int_when_topic_present(tmp_path):
    from telegram_meta import resolve_thread_id

    p = tmp_path / "meta.json"
    _write_meta(p, "foo", {"clarifications": 42})
    assert resolve_thread_id("foo", "clarifications", meta_path=p) == 42


def test_returns_none_when_topic_missing(tmp_path):
    from telegram_meta import resolve_thread_id

    p = tmp_path / "meta.json"
    _write_meta(p, "foo", {})
    assert resolve_thread_id("foo", "clarifications", meta_path=p) is None


def test_returns_none_when_project_missing(tmp_path):
    from telegram_meta import resolve_thread_id

    p = tmp_path / "meta.json"
    _write_meta(p, "other", {"clarifications": 1})
    assert resolve_thread_id("foo", "clarifications", meta_path=p) is None


def test_returns_none_when_meta_file_missing(tmp_path):
    from telegram_meta import resolve_thread_id

    assert (
        resolve_thread_id(
            "foo", "clarifications", meta_path=tmp_path / "no.json"
        )
        is None
    )


def test_feature_flag_disables_lookup(tmp_path, monkeypatch):
    from telegram_meta import resolve_thread_id

    p = tmp_path / "meta.json"
    _write_meta(p, "foo", {"clarifications": 99})
    monkeypatch.setenv("OPENCLAW_TELEGRAM_TOPICS", "0")
    assert resolve_thread_id("foo", "clarifications", meta_path=p) is None
