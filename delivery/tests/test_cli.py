"""Integration tests for cli.py — exercise key subcommands via subprocess."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DELIVERY_DIR = Path(__file__).resolve().parent.parent
_VENV_PY = DELIVERY_DIR / "delivery-venv" / "bin" / "python3"
PYTHON = _VENV_PY if _VENV_PY.exists() else Path(sys.executable)
CLI = DELIVERY_DIR / "cli.py"


def run_cli(args, env_overrides=None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [str(PYTHON), str(CLI), *args],
        capture_output=True, text=True, env=env, cwd=str(DELIVERY_DIR),
    )


class TestCLIBasic(unittest.TestCase):
    def test_version(self):
        r = run_cli(["version"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("0.1.0-wave1", r.stdout)

    def test_help_shows_subcommands(self):
        r = run_cli(["--help"])
        self.assertEqual(r.returncode, 0)
        for cmd in ("activate-spec", "archive-spec", "scan", "proposals", "accept", "reject", "status", "rebuild-state"):
            self.assertIn(cmd, r.stdout)

    def test_status_runs(self):
        r = run_cli(["status"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("openclaw-delivery status", r.stdout)


class TestCLISetSpecRepo(unittest.TestCase):
    def test_set_spec_repo_help(self):
        r = run_cli(["set-spec-repo", "--help"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("--repo", r.stdout)

    def test_set_spec_repo_missing_repo_arg_fails(self):
        r = run_cli(["set-spec-repo", "some/spec.md"])
        self.assertNotEqual(r.returncode, 0)

    def test_set_spec_repo_invalid_repo_format(self):
        # Note: this requires a real active spec to pass precondition,
        # but the regex check runs first — so we can test it without
        # needing real state.
        r = run_cli(["set-spec-repo", "35_specs/nonexistent.md", "--repo", "invalid"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("invalid", r.stderr.lower())

    def test_set_spec_repo_spec_not_active(self):
        r = run_cli(["set-spec-repo", "35_specs/nonexistent.md", "--repo", "bernardTavares/test"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not active", r.stderr.lower())


if __name__ == "__main__":
    unittest.main()
