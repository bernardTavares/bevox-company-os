"""Tests for load_config_yaml + validate_required_fields."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "alert_runner",
    str(Path(__file__).parent.parent / "alert-runner.py"),
)
alert_runner = importlib.util.module_from_spec(_spec)
sys.modules["alert_runner"] = alert_runner
_spec.loader.exec_module(alert_runner)

load_config_yaml = alert_runner.load_config_yaml
validate_required_fields = alert_runner.validate_required_fields


class TestLoadYaml(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_valid_yaml(self):
        p = self.tmp / "ok.yml"
        p.write_text("daily_threshold_usd: 1.50\nenabled: true\n")
        data, warnings = load_config_yaml(p)
        self.assertIsNotNone(data)
        self.assertEqual(data["daily_threshold_usd"], 1.50)
        self.assertEqual(data["enabled"], True)
        self.assertEqual(warnings, [])

    def test_malformed_yaml_returns_none_and_warning(self):
        p = self.tmp / "bad.yml"
        p.write_text("daily_threshold_usd: [unclosed\n")
        data, warnings = load_config_yaml(p)
        self.assertIsNone(data)
        self.assertTrue(any("yaml_parse_error" in w for w in warnings))

    def test_yaml_not_a_dict(self):
        p = self.tmp / "list.yml"
        p.write_text("- just\n- a\n- list\n")
        data, warnings = load_config_yaml(p)
        self.assertIsNone(data)
        self.assertTrue(any("yaml_not_a_dict" in w for w in warnings))

    def test_missing_file(self):
        p = self.tmp / "nope.yml"
        data, warnings = load_config_yaml(p)
        self.assertIsNone(data)
        self.assertTrue(any("yaml_io_error" in w for w in warnings))


class TestValidateRequired(unittest.TestCase):
    def test_threshold_present(self):
        data = {"daily_threshold_usd": 1.50}
        self.assertEqual(validate_required_fields(data), [])

    def test_threshold_missing(self):
        self.assertEqual(validate_required_fields({}), ["daily_threshold_usd"])

    def test_threshold_none(self):
        data = {"daily_threshold_usd": None}
        self.assertEqual(validate_required_fields(data), ["daily_threshold_usd"])

    def test_enabled_optional(self):
        # enabled is NOT required — should not show up in missing
        data = {"daily_threshold_usd": 1.50}
        self.assertEqual(validate_required_fields(data), [])


if __name__ == "__main__":
    unittest.main()
