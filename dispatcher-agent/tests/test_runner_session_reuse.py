"""Tests dispatcher runner session reuse (fresh/resume branching + kill-switch + log header)."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestRunnerSessionReuse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.briefing_path = Path(self.tmp) / "briefing.md"
        self.briefing_path.write_text("# Briefing\nGoal: do X")
        # patch executions dir via store
        from lib import store
        self.exec_dir = Path(self.tmp) / "executions"
        self.exec_dir.mkdir()
        # store.execution_log_path uses store.EXECUTIONS_DIR or similar
        self.patches = []
        # Find the right attr name to patch
        if hasattr(store, "EXECUTIONS_DIR"):
            self.patches.append(patch.object(store, "EXECUTIONS_DIR", self.exec_dir))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)
        os.environ.pop("OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE", None)

    def test_launch_detached_fresh_generates_uuid_when_sprint_has_none(self):
        """sprint_session_id=None → spawn cmd contém --session-id <uuid>, retorna is_fresh=True."""
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id=None,
                sprint_id="sprint-22",
            )
        self.assertTrue(status["sprint_session_was_fresh"])
        self.assertIsNotNone(status["sprint_session_id"])
        cmd_call = mock_run.call_args.args[0]
        self.assertIn("--session-id", cmd_call)
        self.assertNotIn("--resume", cmd_call)

    def test_launch_detached_resume_when_sprint_has_session(self):
        """sprint_session_id="abc-123" → cmd contém --resume, NÃO contém --session-id."""
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id="abc-123-uuid",
                sprint_id="sprint-22",
            )
        self.assertFalse(status["sprint_session_was_fresh"])
        self.assertEqual(status["sprint_session_id"], "abc-123-uuid")
        cmd_call = mock_run.call_args.args[0]
        self.assertIn("--resume", cmd_call)
        self.assertIn("abc-123-uuid", cmd_call)
        self.assertNotIn("--session-id", cmd_call)

    def test_kill_switch_disable_session_reuse_forces_fresh(self):
        """env=1 + sprint_session_id presente → ainda usa --session-id <new>, is_fresh=True."""
        os.environ["OPENCLAW_DISPATCHER_DISABLE_SESSION_REUSE"] = "1"
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id="ignored-uuid",
                sprint_id="sprint-22",
            )
        self.assertTrue(status["sprint_session_was_fresh"])
        self.assertNotEqual(status["sprint_session_id"], "ignored-uuid")
        self.assertTrue(status["kill_switch_active"])
        cmd_call = mock_run.call_args.args[0]
        self.assertIn("--session-id", cmd_call)
        self.assertNotIn("--resume", cmd_call)

    def test_launch_detached_writes_metadata_header_to_log(self):
        """log file deve ter header com metadata pre-spawn."""
        from lib import runner
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            status = runner.launch_detached(
                "T-test", self.briefing_path, "Read,Write",
                sprint_session_id=None,
                sprint_id="sprint-22",
            )
        log_path = Path(status["log_path"])
        content = log_path.read_text()
        self.assertIn("# DISPATCHER METADATA", content)
        self.assertIn("# task_id: T-test", content)
        self.assertIn("# sprint_id: sprint-22", content)
        self.assertIn(f"# execution_session_id: {status['sprint_session_id']}", content)
        self.assertIn("# session_was_fresh: True", content)
        self.assertIn("# ----- claude output below -----", content)

    def test_launch_foreground_supports_session_reuse_same_logic(self):
        """foreground tem mesmo branching que detached."""
        from lib import runner
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = ("ok", "")
            mock_proc.returncode = 0
            mock_proc.pid = 99999
            mock_popen.return_value = mock_proc
            status = runner.launch_foreground(
                "T-fg-test", self.briefing_path, "Read,Write",
                sprint_session_id="fg-abc-uuid",
                sprint_id="sprint-22",
            )
        self.assertFalse(status["sprint_session_was_fresh"])
        self.assertEqual(status["sprint_session_id"], "fg-abc-uuid")
        cmd_call = mock_popen.call_args.args[0]
        self.assertIn("--resume", cmd_call)
        self.assertIn("fg-abc-uuid", cmd_call)


if __name__ == "__main__":
    unittest.main()
