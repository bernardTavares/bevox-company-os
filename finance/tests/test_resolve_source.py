"""Tests for resolve_snapshot_source() precedence."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from runner import resolve_snapshot_source  # noqa: E402


class TestResolveSource(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        self.override = self.tmp / "override.yml"
        self.example = self.tmp / "example.yml"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_override_wins_when_both_exist(self):
        self.override.write_text("as_of: 2026-04-14\n")
        self.example.write_text("as_of: 2026-04-14\n")
        path, source, warnings = resolve_snapshot_source(self.override, self.example)
        self.assertEqual(path, self.override)
        self.assertEqual(source, "override")
        self.assertEqual(warnings, [])

    def test_example_when_only_example_exists(self):
        self.example.write_text("as_of: 2026-04-14\n")
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
