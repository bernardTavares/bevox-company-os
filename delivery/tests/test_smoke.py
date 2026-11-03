"""Smoke test — verifica que agent.py e cli.py importam sem erro."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSmoke(unittest.TestCase):
    def test_import_agent(self):
        import agent  # noqa: F401
        self.assertTrue(hasattr(agent, "VERSION"))
        self.assertTrue(hasattr(agent, "DELIVERY_DIR"))

    def test_import_cli(self):
        import cli  # noqa: F401
        self.assertTrue(hasattr(cli, "main"))

    def test_agent_version_flag(self):
        import agent
        # main() should accept --version and exit 0
        old_argv = sys.argv
        sys.argv = ["agent.py", "--version"]
        try:
            rc = agent.main()
            self.assertEqual(rc, 0)
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
