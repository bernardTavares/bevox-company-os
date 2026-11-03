"""Tests for resolve_snapshot_source() precedence."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

# Load alert-runner.py as module (file has dash in name)
_spec = importlib.util.spec_from_file_location(
    "alert_runner",
    str(Path(__file__).parent.parent / "alert-runner.py"),
)
alert_runner = importlib.util.module_from_spec(_spec)
sys.modules["alert_runner"] = alert_runner
_spec.loader.exec_module(alert_runner)

resolve_snapshot_source = alert_runner.resolve_snapshot_source


class TestResolveSource(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.override = self.tmp / "override.yml"
        self.example = self.tmp / "example.yml"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_override_wins_when_both_exist(self):
        self.override.write_text("daily_threshold_usd: 1.5\n")
        self.example.write_text("daily_threshold_usd: 0.0\n")
        path, source, warnings = resolve_snapshot_source(self.override, self.example)
        self.assertEqual(path, self.override)
        self.assertEqual(source, "override")
        self.assertEqual(warnings, [])

    def test_example_when_only_example_exists(self):
        self.example.write_text("daily_threshold_usd: 0.0\n")
        path, source, warnings = resolve_snapshot_source(self.override, self.example)
        self.assertEqual(path, self.example)
        self.assertEqual(source, "example")
        self.assertIn("no_override_using_example", warnings)

    def test_missing_when_neither_exists(self):
        path, source, warnings = resolve_snapshot_source(self.override, self.example)
        self.assertIsNone(path)
        self.assertEqual(source, "missing")
        self.assertIn("no_canonical_yaml", warnings)


if __name__ == "__main__":
    unittest.main()
