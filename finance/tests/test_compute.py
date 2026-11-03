"""Tests for compute_runway pure function, including edge cases."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from runner import compute_runway  # noqa: E402


class TestComputeRunway(unittest.TestCase):
    def test_profitable_case(self):
        # MRR bem maior que custos → lucrativo, runway null
        r = compute_runway(
            cash_on_hand_brl=125000,
            mrr_brl=18500,
            recurring_costs_monthly_brl=700,
            ai_variable_cost_30d_brl=998.40,
        )
        self.assertEqual(r["burn_monthly_brl"], 1698.40)
        self.assertEqual(r["net_monthly_brl"], 16801.60)
        self.assertTrue(r["is_profitable"])
        self.assertIsNone(r["runway_months"])
        self.assertEqual(r["runway_warnings"], [])

    def test_burning_case(self):
        # MRR baixo, custos altos → nao lucrativo, runway calculado
        r = compute_runway(
            cash_on_hand_brl=125000,
            mrr_brl=500,
            recurring_costs_monthly_brl=2000,
            ai_variable_cost_30d_brl=300,
        )
        # burn = 2300, net = 500 - 2300 = -1800
        self.assertEqual(r["burn_monthly_brl"], 2300)
        self.assertEqual(r["net_monthly_brl"], -1800)
        self.assertFalse(r["is_profitable"])
        # runway = 125000 / 1800 ≈ 69.4
        self.assertAlmostEqual(r["runway_months"], 69.4, places=1)

    def test_break_even(self):
        # net == 0 exato → not profitable, runway null + warning
        r = compute_runway(
            cash_on_hand_brl=125000,
            mrr_brl=1000,
            recurring_costs_monthly_brl=1000,
            ai_variable_cost_30d_brl=0,
        )
        self.assertEqual(r["net_monthly_brl"], 0)
        self.assertFalse(r["is_profitable"])
        self.assertIsNone(r["runway_months"])
        self.assertIn("break_even_no_runway_bound", r["runway_warnings"])

    def test_zero_mrr(self):
        # Nenhuma receita, so custos
        r = compute_runway(
            cash_on_hand_brl=60000,
            mrr_brl=0,
            recurring_costs_monthly_brl=5000,
            ai_variable_cost_30d_brl=1000,
        )
        # burn = 6000, net = -6000, runway = 10.0
        self.assertEqual(r["burn_monthly_brl"], 6000)
        self.assertEqual(r["net_monthly_brl"], -6000)
        self.assertFalse(r["is_profitable"])
        self.assertAlmostEqual(r["runway_months"], 10.0, places=1)

    def test_runway_has_one_decimal_precision(self):
        r = compute_runway(
            cash_on_hand_brl=100000,
            mrr_brl=0,
            recurring_costs_monthly_brl=3333,
            ai_variable_cost_30d_brl=0,
        )
        # 100000 / 3333 = 30.00300..., round to 1 decimal = 30.0
        self.assertEqual(r["runway_months"], 30.0)


if __name__ == "__main__":
    unittest.main()
