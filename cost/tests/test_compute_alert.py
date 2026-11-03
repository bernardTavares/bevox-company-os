"""Tests for compute_alert pure function."""
import importlib.util
import sys
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "alert_runner",
    str(Path(__file__).parent.parent / "alert-runner.py"),
)
alert_runner = importlib.util.module_from_spec(_spec)
sys.modules["alert_runner"] = alert_runner
_spec.loader.exec_module(alert_runner)

compute_alert = alert_runner.compute_alert


class TestComputeAlert(unittest.TestCase):
    def test_below_threshold(self):
        self.assertFalse(compute_alert(True, 1.50, 0.75))

    def test_above_threshold(self):
        self.assertTrue(compute_alert(True, 1.50, 1.85))

    def test_exactly_equal_does_not_fire(self):
        # Strictly greater than; equality does NOT fire
        self.assertFalse(compute_alert(True, 1.50, 1.50))

    def test_disabled_never_fires(self):
        self.assertFalse(compute_alert(False, 1.50, 99.99))

    def test_zero_threshold_never_fires(self):
        # Example mode: threshold = 0 should never fire even with positive cost
        self.assertFalse(compute_alert(True, 0.0, 5.00))

    def test_negative_threshold_never_fires(self):
        # Defensive: <= 0 includes negative
        self.assertFalse(compute_alert(True, -1.0, 0.50))

    def test_zero_cost_below_positive_threshold(self):
        self.assertFalse(compute_alert(True, 1.50, 0.0))


if __name__ == "__main__":
    unittest.main()
