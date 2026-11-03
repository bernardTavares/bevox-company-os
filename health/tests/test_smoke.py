"""Smoke test — verifica que runner.py importa sem erro."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSmoke(unittest.TestCase):
    def test_import_runner(self):
        import runner  # noqa: F401
        self.assertTrue(hasattr(runner, "VERSION"))
        self.assertTrue(hasattr(runner, "HEALTH_DIR"))
        self.assertTrue(hasattr(runner, "STATE_PATH"))
        self.assertTrue(hasattr(runner, "REGISTRY_PATH"))

    def test_pyyaml_importable(self):
        import yaml  # noqa: F401
        self.assertTrue(hasattr(yaml, "safe_load"))

    def test_runner_version(self):
        import runner
        self.assertTrue(runner.VERSION.startswith("0."))


if __name__ == "__main__":
    unittest.main()
