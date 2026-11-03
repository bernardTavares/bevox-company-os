"""Integration tests for cmd_scan end-to-end (mocked checks)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import runner


VALID_REGISTRY_YAML = """\
version: 1
services:
  critical-svc:
    name: "Critical Service"
    owner: Bernard
    epic: E0
    critical: true
    check:
      type: systemd_active
      unit: critical.service
    since: 2026-04-14
  optional-svc:
    name: "Optional Service"
    owner: Bernard
    epic: E1
    critical: false
    check:
      type: systemd_active
      unit: optional.timer
    since: 2026-04-14
"""


class TestCmdScanIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.registry_path = self.tmpdir / "health-registry.yml"
        self.state_path = self.tmpdir / "state.json"
        self.registry_path.write_text(VALID_REGISTRY_YAML)

    def tearDown(self):
        if self.state_path.exists():
            self.state_path.unlink()
        if self.registry_path.exists():
            self.registry_path.unlink()
        self.tmpdir.rmdir()

    def test_scan_all_up_produces_ok(self):
        def mock_run(*args, **kwargs):
            return MagicMock(returncode=0, stdout="active\n", stderr="")

        with patch("subprocess.run", side_effect=mock_run), \
             patch.object(runner, "REGISTRY_PATH", self.registry_path), \
             patch.object(runner, "STATE_PATH", self.state_path):
            rc = runner.cmd_scan()
            self.assertEqual(rc, 0)

        state = json.loads(self.state_path.read_text())
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["overall"]["level"], "ok")
        self.assertEqual(state["overall"]["services_total"], 2)
        self.assertEqual(state["overall"]["services_up"], 2)
        self.assertIn("critical-svc", state["services"])
        self.assertIn("optional-svc", state["services"])

    def test_scan_critical_down_produces_down(self):
        def mock_run(*args, **kwargs):
            cmd = args[0]
            if "critical.service" in cmd:
                return MagicMock(returncode=3, stdout="inactive\n", stderr="")
            return MagicMock(returncode=0, stdout="active\n", stderr="")

        with patch("subprocess.run", side_effect=mock_run), \
             patch.object(runner, "REGISTRY_PATH", self.registry_path), \
             patch.object(runner, "STATE_PATH", self.state_path):
            rc = runner.cmd_scan()
            self.assertEqual(rc, 0)

        state = json.loads(self.state_path.read_text())
        self.assertEqual(state["overall"]["level"], "down")
        self.assertEqual(state["overall"]["critical_not_up"], 1)

    def test_scan_registry_missing_produces_unknown(self):
        self.registry_path.unlink()

        with patch.object(runner, "REGISTRY_PATH", self.registry_path), \
             patch.object(runner, "STATE_PATH", self.state_path):
            rc = runner.cmd_scan()
            self.assertEqual(rc, 0)  # fail-soft: exit 0

        state = json.loads(self.state_path.read_text())
        self.assertEqual(state["overall"]["level"], "unknown")
        self.assertEqual(state["services"], {})
        self.assertIn("not found", state["overall"]["detail"].lower())

    def test_scan_registry_malformed_produces_unknown(self):
        self.registry_path.write_text("this : : is :: invalid ::: yaml")

        with patch.object(runner, "REGISTRY_PATH", self.registry_path), \
             patch.object(runner, "STATE_PATH", self.state_path):
            rc = runner.cmd_scan()
            self.assertEqual(rc, 0)

        state = json.loads(self.state_path.read_text())
        self.assertEqual(state["overall"]["level"], "unknown")

    def test_scan_individual_check_exception_does_not_abort(self):
        def mock_run(*args, **kwargs):
            cmd = args[0]
            if "critical.service" in cmd:
                raise OSError("unexpected!")
            return MagicMock(returncode=0, stdout="active\n", stderr="")

        with patch("subprocess.run", side_effect=mock_run), \
             patch.object(runner, "REGISTRY_PATH", self.registry_path), \
             patch.object(runner, "STATE_PATH", self.state_path):
            rc = runner.cmd_scan()
            self.assertEqual(rc, 0)

        state = json.loads(self.state_path.read_text())
        # Critical got unknown (due to OSError), overall should be down
        self.assertEqual(state["services"]["critical-svc"]["status"], "unknown")
        self.assertEqual(state["overall"]["level"], "down")
        # Other services still ran
        self.assertEqual(state["services"]["optional-svc"]["status"], "up")

    def test_scan_writes_run_id(self):
        def mock_run(*args, **kwargs):
            return MagicMock(returncode=0, stdout="active\n", stderr="")

        with patch("subprocess.run", side_effect=mock_run), \
             patch.object(runner, "REGISTRY_PATH", self.registry_path), \
             patch.object(runner, "STATE_PATH", self.state_path):
            runner.cmd_scan()

        state = json.loads(self.state_path.read_text())
        self.assertTrue(state["run_id"].startswith("run_"))
        self.assertEqual(len(state["run_id"]), 16)  # "run_" + 12 hex chars


class TestCmdStatusAndJson(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_path = self.tmpdir / "state.json"
        self.state_path.write_text(json.dumps({
            "schema_version": 1,
            "generated_at": "2026-04-14T12:00:00.000Z",
            "registry_version": 1,
            "run_id": "run_abc123",
            "duration_ms": 50,
            "overall": {
                "level": "ok",
                "detail": None,
                "critical_total": 2,
                "critical_up": 2,
                "critical_not_up": 0,
                "services_total": 2,
                "services_up": 2,
                "services_degraded": 0,
                "services_down": 0,
                "services_unknown": 0,
            },
            "services": {
                "foo": {
                    "name": "Foo",
                    "epic": "E0",
                    "critical": True,
                    "check_type": "systemd_active",
                    "status": "up",
                    "detail": "active",
                    "checked_at": "2026-04-14T12:00:00.100Z",
                    "duration_ms": 10,
                }
            },
        }))

    def tearDown(self):
        if self.state_path.exists():
            self.state_path.unlink()
        self.tmpdir.rmdir()

    def test_cmd_status_prints_summary(self):
        from io import StringIO
        with patch.object(runner, "STATE_PATH", self.state_path), \
             patch("sys.stdout", new_callable=StringIO) as stdout:
            rc = runner.cmd_status()
            self.assertEqual(rc, 0)
            out = stdout.getvalue()
            self.assertIn("Overall:", out)
            self.assertIn("OK", out)
            self.assertIn("foo", out)

    def test_cmd_status_missing_file_returns_error(self):
        self.state_path.unlink()
        with patch.object(runner, "STATE_PATH", self.state_path):
            rc = runner.cmd_status()
            self.assertNotEqual(rc, 0)

    def test_cmd_json_prints_raw(self):
        from io import StringIO
        with patch.object(runner, "STATE_PATH", self.state_path), \
             patch("sys.stdout", new_callable=StringIO) as stdout:
            rc = runner.cmd_json()
            self.assertEqual(rc, 0)
            out = stdout.getvalue()
            parsed = json.loads(out)
            self.assertEqual(parsed["schema_version"], 1)
            self.assertEqual(parsed["run_id"], "run_abc123")


if __name__ == "__main__":
    unittest.main()
