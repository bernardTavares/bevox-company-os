"""Tests for load_snapshot_yaml + validate_required_fields."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from runner import load_snapshot_yaml, validate_required_fields  # noqa: E402


class TestLoadYaml(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_valid_yaml(self):
        p = self.tmp / "ok.yml"
        p.write_text(
            "as_of: 2026-04-14\n"
            "usd_brl: 5.12\n"
            "cash_on_hand_brl: 125000\n"
            "mrr_brl: 18500\n"
        )
        data, warnings = load_snapshot_yaml(p)
        self.assertIsNotNone(data)
        # YAML parses ISO dates as date objects
        as_of_str = data["as_of"].isoformat() if hasattr(data["as_of"], 'isoformat') else str(data["as_of"])
        self.assertEqual(as_of_str, "2026-04-14")
        self.assertEqual(warnings, [])

    def test_malformed_yaml_returns_none_and_warning(self):
        p = self.tmp / "bad.yml"
        p.write_text("as_of: [unclosed\n")
        data, warnings = load_snapshot_yaml(p)
        self.assertIsNone(data)
        self.assertTrue(any("yaml_parse_error" in w for w in warnings))

    def test_yaml_not_a_dict(self):
        p = self.tmp / "list.yml"
        p.write_text("- just\n- a\n- list\n")
        data, warnings = load_snapshot_yaml(p)
        self.assertIsNone(data)
        self.assertTrue(any("yaml_not_a_dict" in w for w in warnings))

    def test_missing_file(self):
        p = self.tmp / "nope.yml"
        data, warnings = load_snapshot_yaml(p)
        self.assertIsNone(data)
        self.assertTrue(any("yaml_io_error" in w for w in warnings))


class TestValidateRequired(unittest.TestCase):
    def test_all_required_present(self):
        data = {
            "as_of": "2026-04-14",
            "usd_brl": 5.12,
            "cash_on_hand_brl": 125000,
            "mrr_brl": 18500,
        }
        self.assertEqual(validate_required_fields(data), [])

    def test_all_missing(self):
        self.assertEqual(
            sorted(validate_required_fields({})),
            sorted(["as_of", "usd_brl", "cash_on_hand_brl", "mrr_brl"]),
        )

    def test_partial_missing(self):
        data = {"as_of": "2026-04-14", "usd_brl": 5.12}
        self.assertEqual(
            sorted(validate_required_fields(data)),
            sorted(["cash_on_hand_brl", "mrr_brl"]),
        )

    def test_none_value_counts_as_missing(self):
        data = {
            "as_of": "2026-04-14",
            "usd_brl": 5.12,
            "cash_on_hand_brl": None,
            "mrr_brl": 18500,
        }
        self.assertEqual(validate_required_fields(data), ["cash_on_hand_brl"])


if __name__ == "__main__":
    unittest.main()
