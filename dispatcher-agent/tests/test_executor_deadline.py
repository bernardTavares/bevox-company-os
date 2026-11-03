"""Test F3.1: _resolve_max_runtime_seconds + RuntimeMaxSec injection.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F3.1
"""
import unittest
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch


class TestResolveMaxRuntime(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_path = self.tmpdir / "state.json"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_state(self, tasks):
        self.state_path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")

    def test_default_12h_when_no_env_no_payload(self):
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{"id": "T-0001", "status": "ready"}])
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS", None)
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 12 * 3600)

    def test_env_var_override(self):
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{"id": "T-0001", "status": "ready"}])
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "4"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 4 * 3600)

    def test_per_task_payload_override_wins_over_env(self):
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{
            "id": "T-0001",
            "status": "ready",
            "dispatch_payload": {"max_runtime_hours": 24},
        }])
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "4"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 24 * 3600)

    def test_kill_switch_zero_returns_zero(self):
        """env=0 --> no limit (return 0)."""
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{"id": "T-0001", "status": "ready"}])
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "0"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 0)

    def test_corrupted_state_falls_back_to_env(self):
        from lib.runner import _resolve_max_runtime_seconds
        self.state_path.write_text("not json{", encoding="utf-8")
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "6"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 6 * 3600)

    def test_string_override_accepted(self):
        """dispatch_payload.max_runtime_hours = '24' (string) should work."""
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{
            "id": "T-0001",
            "status": "ready",
            "dispatch_payload": {"max_runtime_hours": "24"},
        }])
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "4"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 24 * 3600)

    def test_invalid_string_override_falls_back(self):
        """Non-numeric string override falls back to env."""
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{
            "id": "T-0001",
            "status": "ready",
            "dispatch_payload": {"max_runtime_hours": "not-a-number"},
        }])
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "4"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 4 * 3600)

    def test_fractional_hours_override_preserved(self):
        """0.5h override → 1800s (not 0 from int truncation)."""
        from lib.runner import _resolve_max_runtime_seconds
        self._write_state([{
            "id": "T-0001",
            "status": "ready",
            "dispatch_payload": {"max_runtime_hours": 0.5},
        }])
        with patch("lib.runner._KANBAN_STATE_PATH", self.state_path):
            with patch.dict(os.environ, {"OPENCLAW_EXECUTOR_MAX_RUNTIME_HOURS": "4"}):
                result = _resolve_max_runtime_seconds("T-0001")
        self.assertEqual(result, 1800)


class TestSdCmdInjection(unittest.TestCase):
    """RuntimeMaxSec é adicionado a sd_cmd em launch_detached."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.briefing_path = Path(self.tmp) / "briefing.md"
        self.briefing_path.write_text("# Briefing\nGoal: do X")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_sd_cmd_includes_runtime_max_sec_default(self):
        """Default 12h --> RuntimeMaxSec=43200."""
        from lib import runner
        with patch("lib.runner._resolve_max_runtime_seconds", return_value=43200):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                with patch("lib.runner.store.execution_log_path",
                           return_value=Path("/tmp/test.log")):
                    try:
                        runner.launch_detached(
                            task_id="T-9001",
                            briefing_path=self.briefing_path,
                            allowed_tools="Read",
                        )
                    except Exception:
                        pass  # may raise after mock; only inspect first call
                    args = mock_run.call_args[0][0]
                    self.assertIn("--property=RuntimeMaxSec=43200", args)

    def test_sd_cmd_omits_runtime_max_when_zero(self):
        """Env=0 --> kill switch --> NÃO adicionar property."""
        from lib import runner
        with patch("lib.runner._resolve_max_runtime_seconds", return_value=0):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
                with patch("lib.runner.store.execution_log_path",
                           return_value=Path("/tmp/test.log")):
                    try:
                        runner.launch_detached(
                            task_id="T-9001",
                            briefing_path=self.briefing_path,
                            allowed_tools="Read",
                        )
                    except Exception:
                        pass
                    args = mock_run.call_args[0][0]
                    rt = [a for a in args if "RuntimeMaxSec" in a]
                    self.assertEqual(rt, [])


class TestTimeoutDetection(unittest.TestCase):
    def test_detect_max_runtime_timeout(self):
        from lib.runner import _was_killed_by_max_runtime
        with patch("lib.runner.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "timeout\n", "returncode": 0})()
            self.assertTrue(_was_killed_by_max_runtime("claude-task-T-9001.service"))

    def test_detect_normal_exit(self):
        from lib.runner import _was_killed_by_max_runtime
        with patch("lib.runner.subprocess.run") as mock_run:
            mock_run.return_value = type("R", (), {"stdout": "success\n", "returncode": 0})()
            self.assertFalse(_was_killed_by_max_runtime("claude-task-T-9001.service"))

    def test_detect_subprocess_failure_returns_false(self):
        from lib.runner import _was_killed_by_max_runtime
        with patch("lib.runner.subprocess.run", side_effect=OSError):
            self.assertFalse(_was_killed_by_max_runtime("claude-task-T-9001.service"))


if __name__ == "__main__":
    unittest.main()
