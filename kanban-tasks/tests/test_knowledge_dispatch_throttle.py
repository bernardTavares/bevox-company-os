"""Tests for dispatch_throttle.py (W9.T2.1)."""
import json
import datetime as _dt
from pathlib import Path

from lib.knowledge_watcher.dispatch_throttle import (
    is_throttled, record_dispatch, _DEFAULT_THROTTLE_SECONDS,
)
from lib.knowledge_watcher.state import default_state, write_state


def test_is_throttled_empty_state(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    assert is_throttled("gap-report", state_path) is False


def test_is_throttled_after_record(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    record_dispatch("gap-report", state_path)
    assert is_throttled("gap-report", state_path) is True


def test_different_kinds_independent(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    record_dispatch("gap-report", state_path)
    # retirement-scan kind is not throttled
    assert is_throttled("retirement-scan", state_path) is False


def test_throttle_expires(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    # Manually inject an old timestamp
    s = default_state()
    s["global"]["last_dispatch_at"] = {
        "gap-report": (
            _dt.datetime.now(_dt.timezone.utc)
            - _dt.timedelta(seconds=_DEFAULT_THROTTLE_SECONDS + 10)
        ).isoformat().replace("+00:00", "Z"),
    }
    write_state(state_path, s)
    assert is_throttled("gap-report", state_path) is False


def test_throttle_custom_window(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    record_dispatch("gap-report", state_path)
    # 1s window — should already be expired? No, we just recorded.
    # Custom 60s window confirms not-expired.
    assert is_throttled("gap-report", state_path, throttle_seconds=60) is True


def test_record_dispatch_atomic(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    record_dispatch("gap-report", state_path)
    record_dispatch("retirement-scan", state_path)
    data = json.loads(state_path.read_text())
    assert "gap-report" in data["global"]["last_dispatch_at"]
    assert "retirement-scan" in data["global"]["last_dispatch_at"]


def test_record_dispatch_no_state_file(tmp_path):
    """No prior state.json → record_dispatch creates it gracefully."""
    state_path = tmp_path / "nope.json"
    record_dispatch("gap-report", state_path)
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "gap-report" in data["global"]["last_dispatch_at"]


def test_is_throttled_handles_missing_state(tmp_path):
    state_path = tmp_path / "nope.json"
    # No file → never throttled
    assert is_throttled("gap-report", state_path) is False


def test_is_throttled_handles_malformed_timestamp(tmp_path):
    state_path = tmp_path / "state.json"
    s = default_state()
    s["global"]["last_dispatch_at"] = {"gap-report": "not-a-date"}
    write_state(state_path, s)
    # Malformed → not throttled (defensive)
    assert is_throttled("gap-report", state_path) is False
