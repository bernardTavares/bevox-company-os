"""Tests cmd_next session_id propagation."""
import argparse
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCmdNextSessionPropagation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / "state.json"
        self._write_state(execution_session_id=None)
        from lib import selector
        self.selector_patch = patch.object(selector, "KANBAN_STATE", self.state_path)
        self.selector_patch.start()

    def tearDown(self):
        self.selector_patch.stop()
        shutil.rmtree(self.tmp)
        os.environ.pop("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE", None)

    def _write_state(self, execution_session_id):
        sprint = {"id": "sprint-22", "state": "current", "project": "test-project"}
        if execution_session_id is not None:
            sprint["execution_session_id"] = execution_session_id
        self.state_path.write_text(json.dumps({
            "schema_version": 4,
            "sprints": [sprint],
            "tasks": [
                {"id": "T-1", "title": "x", "status": "ready",
                 "sprint_id": "sprint-22", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {"goal": "do X",
                                       "acceptance_criteria": ["x"],
                                       "spec_ref": "n/a"}},
            ],
        }))

    def _build_args(self, **overrides):
        args = argparse.Namespace(
            project="test-project",
            launch=True,
            foreground=False,
            no_tester=False,
            json=False,
            model=None,
            allowed_tools=None,
            briefing_only=False,
            **overrides,
        )
        return args

    def _common_patches(self):
        """Return list of patch context managers shared across tests."""
        briefing_path = Path(self.tmp) / "briefing.md"
        briefing_path.write_text("# B")
        return [
            patch("lib.briefing.render_briefing", return_value="# B"),
            patch("lib.store.write_briefing", return_value=briefing_path),
            patch("lib.lifecycle.move_to_in_progress"),
            patch("lib.lifecycle.merge_dispatch_payload"),
            patch("subprocess.run",
                  return_value=MagicMock(returncode=0, stdout="{}", stderr="")),
        ]

    def test_cmd_next_first_dispatch_calls_kanban_set_session_id(self):
        """Sprint sem session_id → runner is_fresh=True → cmd_next chama kanban set-session-id."""
        from lib import api
        patches = self._common_patches()
        import contextlib
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            mock_launch = stack.enter_context(
                patch("lib.runner.launch_detached")
            )
            mock_subproc = stack.enter_context(
                patch("lib.api.subprocess.run",
                      return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
            )
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts",
                "sprint_session_id": "fresh-uuid-abc",
                "sprint_session_was_fresh": True,
                "kill_switch_active": False,
                "started_at": "2026-04-25T00:00:00Z", "log_path": "/tmp/x.log",
                "run_mode": "detach", "pid": 12345,
                "briefing_path": str(Path(self.tmp) / "briefing.md"),
            }
            args = self._build_args()
            api.cmd_next(args)
        kanban_calls = [c for c in mock_subproc.call_args_list
                        if any("set-session-id" in str(arg) for arg in c.args[0])]
        self.assertGreaterEqual(len(kanban_calls), 1, "expected kanban set-session-id call")
        cmd = kanban_calls[0].args[0]
        self.assertIn("fresh-uuid-abc", cmd)
        self.assertIn("sprint-22", cmd)

    def test_cmd_next_resume_does_not_call_set_session_id(self):
        """Sprint COM session_id → runner is_fresh=False → kanban NÃO tocado."""
        self._write_state(execution_session_id="existing-uuid")
        from lib import api
        patches = self._common_patches()
        import contextlib
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            mock_launch = stack.enter_context(
                patch("lib.runner.launch_detached")
            )
            mock_subproc = stack.enter_context(
                patch("lib.api.subprocess.run",
                      return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
            )
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts",
                "sprint_session_id": "existing-uuid",
                "sprint_session_was_fresh": False,
                "kill_switch_active": False,
                "started_at": "2026-04-25T00:00:00Z", "log_path": "/tmp/x.log",
                "run_mode": "detach", "pid": 12345,
                "briefing_path": str(Path(self.tmp) / "briefing.md"),
            }
            args = self._build_args()
            api.cmd_next(args)
        kanban_calls = [c for c in mock_subproc.call_args_list
                        if any("set-session-id" in str(arg) for arg in c.args[0])]
        self.assertEqual(len(kanban_calls), 0, "kanban set-session-id should NOT be called on resume")

    def test_cmd_next_kill_switch_skips_set_session_id(self):
        """Kill-switch ativo + runner is_fresh=True → kanban NÃO tocado."""
        os.environ["OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE"] = "1"
        from lib import api
        patches = self._common_patches()
        import contextlib
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            mock_launch = stack.enter_context(
                patch("lib.runner.launch_detached")
            )
            mock_subproc = stack.enter_context(
                patch("lib.api.subprocess.run",
                      return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
            )
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts",
                "sprint_session_id": "killswitch-fresh-uuid",
                "sprint_session_was_fresh": True,
                "kill_switch_active": True,
                "started_at": "2026-04-25T00:00:00Z", "log_path": "/tmp/x.log",
                "run_mode": "detach", "pid": 12345,
                "briefing_path": str(Path(self.tmp) / "briefing.md"),
            }
            args = self._build_args()
            api.cmd_next(args)
        kanban_calls = [c for c in mock_subproc.call_args_list
                        if any("set-session-id" in str(arg) for arg in c.args[0])]
        self.assertEqual(len(kanban_calls), 0, "kanban should NOT be touched when kill-switch active")


if __name__ == "__main__":
    unittest.main()
