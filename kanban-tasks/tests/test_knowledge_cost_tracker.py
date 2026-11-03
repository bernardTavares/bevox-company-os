"""Tests for F3 cost tracking (W8.T1.2)."""
import json
from pathlib import Path

from lib.knowledge_watcher.cost_tracker import (
    record_f3_cost, read_cost_summary,
)
from lib.knowledge_watcher.state import default_state, write_state


def test_record_f3_cost_creates_history(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())

    record_f3_cost(state_path, 1.20, today="2026-05-10")
    record_f3_cost(state_path, 0.50, today="2026-05-15")

    data = json.loads(state_path.read_text())
    assert data["global"]["f3_cost_history"]["2026-05"] == 1.70
    assert data["global"]["f3_cost_total_lifetime_usd"] == 1.70


def test_record_f3_cost_separate_months(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())

    record_f3_cost(state_path, 1.0, today="2026-05-15")
    record_f3_cost(state_path, 2.0, today="2026-06-01")

    data = json.loads(state_path.read_text())
    assert data["global"]["f3_cost_history"]["2026-05"] == 1.0
    assert data["global"]["f3_cost_history"]["2026-06"] == 2.0
    assert data["global"]["f3_cost_total_lifetime_usd"] == 3.0


def test_record_f3_cost_zero_or_negative_noop(tmp_path):
    """Zero and negative values are no-ops (don't create empty history entries)."""
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())

    record_f3_cost(state_path, 0.0, today="2026-05-10")
    record_f3_cost(state_path, -0.5, today="2026-05-10")

    data = json.loads(state_path.read_text())
    assert "f3_cost_history" not in data["global"] or \
        data["global"]["f3_cost_history"].get("2026-05", 0) == 0


def test_read_cost_summary(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    record_f3_cost(state_path, 1.20, today="2026-05-10")

    summary = read_cost_summary(state_path, today="2026-05-31")
    assert summary["f3_cost_mtd_usd"] == 1.20
    assert summary["f3_cost_lifetime_usd"] == 1.20
    assert summary["budget_remaining_mtd_usd"] == 5.0 - 1.20
    assert summary["budget_monthly_usd"] == 5.0


def test_read_cost_summary_missing_state_returns_zeros(tmp_path):
    """No state file → all zeros + full budget remaining."""
    state_path = tmp_path / "no-state.json"
    summary = read_cost_summary(state_path, today="2026-05-31")
    assert summary["f3_cost_mtd_usd"] == 0
    assert summary["f3_cost_lifetime_usd"] == 0
    assert summary["budget_remaining_mtd_usd"] == 5.0


def test_read_cost_summary_other_month_isolated(tmp_path):
    """MTD only counts current month; lifetime sums all."""
    state_path = tmp_path / "state.json"
    write_state(state_path, default_state())
    record_f3_cost(state_path, 1.0, today="2026-05-15")
    record_f3_cost(state_path, 3.0, today="2026-06-01")

    s = read_cost_summary(state_path, today="2026-06-15")
    assert s["f3_cost_mtd_usd"] == 3.0
    assert s["f3_cost_lifetime_usd"] == 4.0
