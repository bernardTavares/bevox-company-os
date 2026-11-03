"""Tests for build_state orchestrator + write_state_atomic."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from runner import build_state, write_state_atomic  # noqa: E402
import runner  # noqa: E402


class TestBuildState(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.override = self.tmp / "override.yml"
        self.example = self.tmp / "example.yml"
        self.state_file = self.tmp / "state.json"
        self.db = self.tmp / "cost.db"
        self._init_db()
        self._patch()

    def tearDown(self):
        self._unpatch()
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

    def _patch(self):
        self._orig_override = runner.OVERRIDE_PATH
        self._orig_example = runner.EXAMPLE_PATH
        self._orig_state = runner.STATE_PATH
        runner.OVERRIDE_PATH = self.override
        runner.EXAMPLE_PATH = self.example
        runner.STATE_PATH = self.state_file

    def _unpatch(self):
        runner.OVERRIDE_PATH = self._orig_override
        runner.EXAMPLE_PATH = self._orig_example
        runner.STATE_PATH = self._orig_state

    def test_missing_source(self):
        state = build_state(cost_db_path=self.db)
        self.assertEqual(state["status"], "no_canonical_yaml")
        self.assertEqual(state["inputs"]["snapshot_source"], "missing")
        self.assertIsNone(state["runway_months"])
        self.assertIn("no_canonical_yaml", state["warnings"])

    def test_example_fallback(self):
        self.example.write_text(
            "as_of: 2026-04-14\n"
            "usd_brl: 5.00\n"
            "cash_on_hand_brl: 0\n"
            "mrr_brl: 0\n"
            "recurring_costs_brl: []\n"
        )
        state = build_state(cost_db_path=self.db)
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["inputs"]["snapshot_source"], "example")
        self.assertIn("no_override_using_example", state["warnings"])

    def test_override_with_real_values(self):
        from datetime import date
        today = date(2026, 4, 14)
        self._insert_cost(today.isoformat(), 0.50)

        self.override.write_text(
            "as_of: 2026-04-14\n"
            "usd_brl: 5.00\n"
            "cash_on_hand_brl: 125000\n"
            "mrr_brl: 18500\n"
            "recurring_costs_brl:\n"
            "  - name: Hetzner\n"
            "    category: infra\n"
            "    amount_brl: 450\n"
            "  - name: GitHub\n"
            "    category: saas\n"
            "    amount_brl: 250\n"
        )

        state = build_state(cost_db_path=self.db, today=today)

        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["inputs"]["snapshot_source"], "override")
        self.assertEqual(state["cash_on_hand_brl"], 125000)
        self.assertEqual(state["mrr_brl"], 18500)
        self.assertEqual(state["recurring_costs_monthly_brl"], 700)
        self.assertAlmostEqual(state["ai_variable_cost_30d_usd"], 0.50, places=4)
        # 0.50 * 5.00 = 2.50
        self.assertAlmostEqual(state["ai_variable_cost_30d_brl"], 2.50, places=2)
        # burn = 700 + 2.50 = 702.50; net = 18500 - 702.50 = 17797.50; profitable
        self.assertEqual(state["burn_monthly_brl"], 702.50)
        self.assertEqual(state["net_monthly_brl"], 17797.50)
        self.assertTrue(state["is_profitable"])
        self.assertIsNone(state["runway_months"])
        self.assertEqual(len(state["recurring_costs_breakdown"]), 2)

    def test_incomplete_yaml(self):
        self.override.write_text("as_of: 2026-04-14\nusd_brl: 5.00\n")
        state = build_state(cost_db_path=self.db)
        self.assertEqual(state["status"], "incomplete_yaml")
        self.assertIn("cash_on_hand_brl", state["missing_fields"])
        self.assertIn("mrr_brl", state["missing_fields"])
        self.assertIsNone(state["runway_months"])

    def test_cost_db_missing_still_computes(self):
        # Override valido, mas cost DB nao existe → segue com ai_variable = 0
        self.override.write_text(
            "as_of: 2026-04-14\n"
            "usd_brl: 5.00\n"
            "cash_on_hand_brl: 125000\n"
            "mrr_brl: 18500\n"
            "recurring_costs_brl:\n"
            "  - name: Hetzner\n"
            "    category: infra\n"
            "    amount_brl: 450\n"
        )
        state = build_state(cost_db_path=self.tmp / "nope.db")
        self.assertEqual(state["status"], "ok")
        self.assertIn("e9_cost_db_missing", state["warnings"])
        self.assertEqual(state["ai_variable_cost_30d_usd"], 0)
        self.assertEqual(state["ai_variable_cost_30d_brl"], 0)
        # burn = 450, net = 18500 - 450 = 18050, profitable
        self.assertEqual(state["burn_monthly_brl"], 450)
        self.assertEqual(state["net_monthly_brl"], 18050)


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
