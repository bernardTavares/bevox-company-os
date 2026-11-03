"""Tests for read_today_cost_usd against a real SQLite fixture."""
import importlib.util
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

read_today_cost_usd = alert_runner.read_today_cost_usd


class TestTodayCostReader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db = Path(self.tmpdir.name) / "test.db"
        conn = sqlite3.connect(self.db)
        conn.execute(
            """
            CREATE TABLE usage_snapshots (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              timestamp INTEGER NOT NULL,
              date TEXT NOT NULL,
              hour INTEGER NOT NULL,
              agent_id TEXT NOT NULL,
              model TEXT NOT NULL,
              input_tokens INTEGER NOT NULL,
              output_tokens INTEGER NOT NULL,
              total_tokens INTEGER NOT NULL,
              cost REAL NOT NULL,
              created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
            """
        )
        conn.commit()
        self.conn = conn

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def _insert(self, date_str: str, cost: float):
        self.conn.execute(
            "INSERT INTO usage_snapshots (timestamp, date, hour, agent_id, model, "
            "input_tokens, output_tokens, total_tokens, cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (0, date_str, 0, "main", "openai/gpt-5.4", 100, 50, 150, cost),
        )
        self.conn.commit()

    def test_missing_db_returns_zero(self):
        nonexistent = Path(self.tmpdir.name) / "nope.db"
        cost, warnings = read_today_cost_usd(nonexistent, date(2026, 4, 15))
        self.assertEqual(cost, 0.0)
        self.assertIn("cost_db_missing", warnings)

    def test_empty_db_returns_zero_no_warning(self):
        cost, warnings = read_today_cost_usd(self.db, date(2026, 4, 15))
        self.assertEqual(cost, 0.0)
        self.assertEqual(warnings, [])

    def test_single_row_today(self):
        today = date(2026, 4, 15)
        self._insert(today.isoformat(), 0.50)
        cost, warnings = read_today_cost_usd(self.db, today)
        self.assertAlmostEqual(cost, 0.50, places=4)
        self.assertEqual(warnings, [])

    def test_row_yesterday_excluded(self):
        today = date(2026, 4, 15)
        self._insert("2026-04-14", 999.99)  # yesterday UTC
        cost, warnings = read_today_cost_usd(self.db, today)
        self.assertEqual(cost, 0.0)
        self.assertEqual(warnings, [])

    def test_sum_multiple_rows_today(self):
        today = date(2026, 4, 15)
        self._insert(today.isoformat(), 0.30)
        self._insert(today.isoformat(), 0.25)
        self._insert(today.isoformat(), 0.45)
        cost, warnings = read_today_cost_usd(self.db, today)
        self.assertAlmostEqual(cost, 1.00, places=4)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
