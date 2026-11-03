"""Tests for scripts/init_telegram_topics.py."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to path so we can import the module under test
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture
def meta_file(tmp_path):
    """Create a projects-meta.json fixture and return its path."""
    p = tmp_path / "projects-meta.json"
    p.write_text(json.dumps({
        "projects": [
            {
                "id": "myproj",
                "name": "MyProj",
                "bot_id": "voz-myproj",
                "bot_username": "voz_myproj_bot",
                "bot_port": 18765,
                "telegram": {"chat_id": -100123, "topics": {}},
            }
        ]
    }))
    return p


def _ok_response(thread_id: int):
    """Mock requests-style response for a successful createForumTopic."""
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {
        "ok": True,
        "result": {"message_thread_id": thread_id, "name": "x"},
    }
    return r


def test_creates_all_canonical_topics_when_none_exist(meta_file, monkeypatch):
    """No topics yet → all 4 canonical topics are created (clarifications,
    dispatcher, blocks, knowledge)."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake-token-123")

    import importlib
    mod = importlib.import_module("init_telegram_topics")

    with patch.object(mod.requests, "post", side_effect=[
        _ok_response(11),
        _ok_response(22),
        _ok_response(33),
        _ok_response(44),
    ]):
        result = mod.run(slug="myproj", meta_path=meta_file)

    assert result["created"] == ["clarifications", "dispatcher", "blocks", "knowledge"]
    assert result["existing"] == []
    assert result["failed"] == []

    meta = json.loads(meta_file.read_text())
    proj = next(p for p in meta["projects"] if p["id"] == "myproj")
    assert proj["telegram"]["topics"] == {
        "clarifications": 11,
        "dispatcher": 22,
        "blocks": 33,
        "knowledge": 44,
    }


def test_skips_topics_already_present(meta_file, monkeypatch):
    """Pre-existing topics in meta → only missing ones are created."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake-token-123")

    meta = json.loads(meta_file.read_text())
    next(p for p in meta["projects"] if p["id"] == "myproj")[
        "telegram"
    ]["topics"]["clarifications"] = 99
    meta_file.write_text(json.dumps(meta))

    import importlib
    mod = importlib.import_module("init_telegram_topics")

    with patch.object(mod.requests, "post",
                      side_effect=[_ok_response(22), _ok_response(33), _ok_response(44)]) as post_mock:
        result = mod.run(slug="myproj", meta_path=meta_file)

    assert result["created"] == ["dispatcher", "blocks", "knowledge"]
    assert result["existing"] == ["clarifications"]
    assert post_mock.call_count == 3

    meta = json.loads(meta_file.read_text())
    proj = next(p for p in meta["projects"] if p["id"] == "myproj")
    assert proj["telegram"]["topics"] == {
        "clarifications": 99,
        "dispatcher": 22,
        "blocks": 33,
        "knowledge": 44,
    }


def test_partial_failure_returns_partial_state(meta_file, monkeypatch):
    """Telegram API rejects one topic → meta updated only for successes."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake-token-123")

    fail_resp = MagicMock()
    fail_resp.status_code = 400
    fail_resp.json.return_value = {"ok": False, "description": "BAD_REQUEST"}

    import importlib
    mod = importlib.import_module("init_telegram_topics")

    with patch.object(mod.requests, "post",
                      side_effect=[_ok_response(11), fail_resp, _ok_response(33), _ok_response(44)]):
        result = mod.run(slug="myproj", meta_path=meta_file)

    assert result["created"] == ["clarifications", "blocks", "knowledge"]
    assert result["failed"] == [
        {"topic": "dispatcher", "error": "BAD_REQUEST"}
    ]

    meta = json.loads(meta_file.read_text())
    proj = next(p for p in meta["projects"] if p["id"] == "myproj")
    assert proj["telegram"]["topics"] == {"clarifications": 11, "blocks": 33, "knowledge": 44}


def test_fails_when_bot_token_missing(meta_file, monkeypatch):
    """No BOT_TOKEN_<UPPER_SLUG> env → InitTopicsError raised."""
    monkeypatch.delenv("BOT_TOKEN_VOZ_MYPROJ", raising=False)

    import importlib
    mod = importlib.import_module("init_telegram_topics")

    with pytest.raises(mod.InitTopicsError) as exc:
        mod.run(slug="myproj", meta_path=meta_file)
    assert "token" in str(exc.value).lower()


def test_fails_when_chat_id_missing(meta_file, monkeypatch):
    """No telegram.chat_id in meta → InitTopicsError raised."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_MYPROJ", "fake")

    meta = json.loads(meta_file.read_text())
    next(p for p in meta["projects"] if p["id"] == "myproj")["telegram"].pop(
        "chat_id"
    )
    meta_file.write_text(json.dumps(meta))

    import importlib
    mod = importlib.import_module("init_telegram_topics")

    with pytest.raises(mod.InitTopicsError) as exc:
        mod.run(slug="myproj", meta_path=meta_file)
    assert "chat_id" in str(exc.value).lower()


def test_fails_when_project_not_found(meta_file, monkeypatch):
    """Slug missing from meta → InitTopicsError raised."""
    monkeypatch.setenv("BOT_TOKEN_VOZ_OTHER", "fake")

    import importlib
    mod = importlib.import_module("init_telegram_topics")

    with pytest.raises(mod.InitTopicsError) as exc:
        mod.run(slug="other", meta_path=meta_file)
    assert "not found" in str(exc.value).lower()
