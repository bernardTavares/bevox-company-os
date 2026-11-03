"""Tests for build_state orchestrator + write_state_atomic."""
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "alert_runner",
    str(Path(__file__).parent.parent / "alert-runner.py"),
)
alert_runner = importlib.util.module_from_spec(_spec)
sys.modules["alert_runner"] = alert_runner
_spec.loader.exec_module(alert_runner)

build_state = alert_runner.build_state
write_state_atomic = alert_runner.write_state_atomic


class TestBuildState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.override = self.tmp / "override.yml"
        self.example = self.tmp / "example.yml"
        self.state_file = self.tmp / "state.json"
        self.db = self.tmp / "cost.db"
        self._init_db()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _init_db(self):
        conn = sqlite3.connect(self.db)
        conn.execute(
            "CREATE TABLE usage_snapshots ("
            "id INTEGER PRIMARY KEY, timestamp INTEGER, date TEXT, hour INTEGER, "
            "agent_id TEXT, model TEXT, input_tokens INTEGER, output_tokens INTEGER, "
            "total_tokens INTEGER, cost REAL)"
        )
        conn.commit()
        conn.close()

    def _insert_cost(self, date_str: str, cost: float):
        conn = sqlite3.connect(self.db)
        conn.execute(
            "INSERT INTO usage_snapshots VALUES (NULL, 0, ?, 0, 'main', 'openai/gpt-5.4', 100, 50, 150, ?)",
            (date_str, cost),
        )
        conn.commit()
        conn.close()

    def test_missing_source(self):
        state = build_state(cost_db_path=self.db, today_utc=date(2026, 4, 15),
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["status"], "no_config")
        self.assertEqual(state["config_source"], "missing")
        self.assertFalse(state["alert_active"])
        self.assertIsNone(state["daily_threshold_usd"])
        self.assertEqual(state["today_date"], "2026-04-15")
        self.assertIn("no_canonical_yaml", state["warnings"])

    def test_example_fallback_threshold_zero(self):
        self.example.write_text("daily_threshold_usd: 0.0\nenabled: true\n")
        self._insert_cost("2026-04-15", 5.00)
        state = build_state(cost_db_path=self.db, today_utc=date(2026, 4, 15),
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["config_source"], "example")
        self.assertIn("no_override_using_example", state["warnings"])
        self.assertEqual(state["daily_threshold_usd"], 0.0)
        # Threshold = 0 → never fires, even with positive cost
        self.assertFalse(state["alert_active"])
        self.assertEqual(state["today_cost_usd"], 5.0)
        self.assertIsNone(state["today_cost_pct_of_threshold"])

    def test_override_below_threshold(self):
        today = date(2026, 4, 15)
        self._insert_cost(today.isoformat(), 0.75)
        self.override.write_text("daily_threshold_usd: 1.50\nenabled: true\n")
        state = build_state(cost_db_path=self.db, today_utc=today,
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["config_source"], "override")
        self.assertEqual(state["daily_threshold_usd"], 1.50)
        self.assertEqual(state["today_cost_usd"], 0.75)
        self.assertEqual(state["today_cost_pct_of_threshold"], 50.0)
        self.assertFalse(state["alert_active"])

    def test_override_above_threshold_fires(self):
        today = date(2026, 4, 15)
        self._insert_cost(today.isoformat(), 1.85)
        self.override.write_text("daily_threshold_usd: 1.50\nenabled: true\n")
        state = build_state(cost_db_path=self.db, today_utc=today,
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["status"], "ok")
        self.assertTrue(state["alert_active"])
        self.assertEqual(state["today_cost_pct_of_threshold"], 123.3)

    def test_disabled_suppresses_alert(self):
        today = date(2026, 4, 15)
        self._insert_cost(today.isoformat(), 99.99)  # way over threshold
        self.override.write_text("daily_threshold_usd: 1.50\nenabled: false\n")
        state = build_state(cost_db_path=self.db, today_utc=today,
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["status"], "disabled")
        self.assertFalse(state["alert_active"])
        # Cost still reported even when disabled
        self.assertEqual(state["today_cost_usd"], 99.99)

    def test_missing_required_fields(self):
        self.override.write_text("enabled: true\n")  # threshold missing
        state = build_state(cost_db_path=self.db, today_utc=date(2026, 4, 15),
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["status"], "error")
        self.assertIn("daily_threshold_usd", state["missing_fields"])
        self.assertFalse(state["alert_active"])

    def test_cost_db_missing_does_not_fail(self):
        self.override.write_text("daily_threshold_usd: 1.50\n")
        state = build_state(cost_db_path=self.tmp / "nope.db", today_utc=date(2026, 4, 15),
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["status"], "ok")
        self.assertIn("cost_db_missing", state["warnings"])
        self.assertEqual(state["today_cost_usd"], 0.0)
        self.assertFalse(state["alert_active"])  # cost = 0 < threshold

    def test_today_date_matches_input_utc(self):
        state = build_state(cost_db_path=self.db, today_utc=date(2026, 12, 31),
                           override_path=self.override, example_path=self.example)
        self.assertEqual(state["today_date"], "2026-12-31")


class TestAtomicWrite(unittest.TestCase):
    def test_write_creates_dir_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "state.json"
            write_state_atomic({"hello": "world"}, path=target)
            self.assertTrue(target.exists())
            data = json.loads(target.read_text())
            self.assertEqual(data, {"hello": "world"})

    def test_write_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "state.json"
            write_state_atomic({"v": 1}, path=target)
            write_state_atomic({"v": 2}, path=target)
            data = json.loads(target.read_text())
            self.assertEqual(data["v"], 2)


if __name__ == "__main__":
    unittest.main()
