"""Tests cron audit jsonl includes execution_session_id + session_was_fresh em dispatched outcome."""
import unittest
from unittest.mock import MagicMock


class TestCronAuditSessionId(unittest.TestCase):
    def test_cron_action_dispatched_includes_execution_session_id(self):
        """outcome=dispatched action dict tem execution_session_id + session_was_fresh."""
        from lib import cron
        dispatch_one_fn = MagicMock(return_value={
            "outcome": "dispatched",
            "task_id": "T-1",
            "execution_session_id": "abc-uuid",
            "session_was_fresh": True,
        })
        check_blocks_fn = MagicMock(return_value=(False, ""))
        stats = cron.process_projects(
            opted_in=["test-project"],
            dry_run=False,
            dispatch_one_fn=dispatch_one_fn,
            check_blocks_fn=check_blocks_fn,
        )
        action_dicts = stats["actions_per_project"]
        self.assertEqual(len(action_dicts), 1)
        a = action_dicts[0]
        self.assertEqual(a["outcome"], "dispatched")
        self.assertEqual(a.get("execution_session_id"), "abc-uuid")
        self.assertTrue(a.get("session_was_fresh"))

    def test_cron_action_skipped_omits_execution_session_id(self):
        """skipped_no_ready NÃO tem session fields (ausente → None via .get)."""
        from lib import cron
        dispatch_one_fn = MagicMock(return_value={
            "outcome": "skipped_no_ready",
            "task_id": None,
            "skip_reason": "no ready",
        })
        check_blocks_fn = MagicMock(return_value=(False, ""))
        stats = cron.process_projects(
            opted_in=["test-project"],
            dry_run=False,
            dispatch_one_fn=dispatch_one_fn,
            check_blocks_fn=check_blocks_fn,
        )
        action_dicts = stats["actions_per_project"]
        self.assertEqual(len(action_dicts), 1)
        a = action_dicts[0]
        self.assertEqual(a["outcome"], "skipped_no_ready")
        # campo session fields ausentes para skipped (NOT propagated when missing)
        self.assertIsNone(a.get("execution_session_id"))
        self.assertIsNone(a.get("session_was_fresh"))


class TestDispatchOneForProjectSessionPropagation(unittest.TestCase):
    """Direct test do _dispatch_one_for_project — caminho de produção."""

    def setUp(self):
        import json
        import shutil
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / "state.json"
        self._json = json
        self._Path = Path
        self._shutil = shutil
        self._write_state(execution_session_id=None)
        from lib import selector
        self.selector_patch = patch.object(selector, "KANBAN_STATE", self.state_path)
        self.selector_patch.start()

    def tearDown(self):
        import os as os_mod
        self.selector_patch.stop()
        self._shutil.rmtree(self.tmp)
        os_mod.environ.pop("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE", None)

    def _write_state(self, execution_session_id):
        sprint = {"id": "sprint-22", "state": "current", "project": "test-project"}
        if execution_session_id is not None:
            sprint["execution_session_id"] = execution_session_id
        self.state_path.write_text(self._json.dumps({
            "schema_version": 4,
            "sprints": [sprint],
            "tasks": [],
        }))

    def test_dispatch_one_propagates_session_id_from_sprint(self):
        """_dispatch_one_for_project lê execution_session_id da sprint e passa ao runner."""
        self._write_state(execution_session_id="existing-uuid")
        from lib import cron
        from unittest.mock import patch, MagicMock
        import subprocess as subprocess_mod
        task = {"id": "T-1", "sprint_id": "sprint-22", "project": "test-project",
                "dispatch_payload": {"goal": "x", "acceptance_criteria": ["x"], "spec_ref": "n/a"}}
        with patch("lib.runner.launch_detached") as mock_launch, \
             patch("lib.briefing.render_briefing", return_value="# B"), \
             patch("lib.store.write_briefing") as mock_store_briefing, \
             patch("lib.selector.select_next_ready", return_value=task), \
             patch.object(subprocess_mod, "run") as mock_subproc:
            mock_store_briefing.return_value = self._Path(self.tmp) / "briefing.md"
            (self._Path(self.tmp) / "briefing.md").write_text("# B")
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts", "pid": 9999,
                "sprint_session_id": "existing-uuid",
                "sprint_session_was_fresh": False,
                "kill_switch_active": False,
                "started_at": "2026-04-25T00:00:00Z", "log_path": "/tmp/x.log",
                "run_mode": "detach",
            }
            mock_subproc.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            result = cron._dispatch_one_for_project("test-project")
        # Verify launch_detached recebeu sprint_session_id + sprint_id
        call_kwargs = mock_launch.call_args.kwargs
        self.assertEqual(call_kwargs.get("sprint_session_id"), "existing-uuid")
        self.assertEqual(call_kwargs.get("sprint_id"), "sprint-22")
        # Verify result tem session fields
        self.assertEqual(result.get("execution_session_id"), "existing-uuid")
        self.assertFalse(result.get("session_was_fresh"))

    def test_dispatch_one_calls_kanban_set_session_id_when_fresh(self):
        """_dispatch_one_for_project chama kanban set-session-id quando is_fresh + kill-switch off."""
        self._write_state(execution_session_id=None)
        from lib import cron
        from unittest.mock import patch, MagicMock
        import subprocess as subprocess_mod
        task = {"id": "T-1", "sprint_id": "sprint-22", "project": "test-project",
                "dispatch_payload": {"goal": "x", "acceptance_criteria": ["x"], "spec_ref": "n/a"}}
        with patch("lib.runner.launch_detached") as mock_launch, \
             patch("lib.briefing.render_briefing", return_value="# B"), \
             patch("lib.store.write_briefing") as mock_store_briefing, \
             patch("lib.selector.select_next_ready", return_value=task), \
             patch.object(subprocess_mod, "run") as mock_subproc:
            mock_store_briefing.return_value = self._Path(self.tmp) / "briefing.md"
            (self._Path(self.tmp) / "briefing.md").write_text("# B")
            mock_launch.return_value = {
                "task_id": "T-1", "session_id": "T-1-ts", "pid": 9999,
                "sprint_session_id": "fresh-uuid-abc",
                "sprint_session_was_fresh": True,
                "kill_switch_active": False,
                "started_at": "2026-04-25T00:00:00Z", "log_path": "/tmp/x.log",
                "run_mode": "detach",
            }
            mock_subproc.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            cron._dispatch_one_for_project("test-project")
        # Verify kanban CLI invocado com set-session-id
        kanban_calls = [c for c in mock_subproc.call_args_list
                        if any("set-session-id" in str(arg) for arg in c.args[0])]
        self.assertGreaterEqual(len(kanban_calls), 1)
        cmd = kanban_calls[0].args[0]
        self.assertIn("fresh-uuid-abc", cmd)
        self.assertIn("sprint-22", cmd)


if __name__ == "__main__":
    unittest.main()
