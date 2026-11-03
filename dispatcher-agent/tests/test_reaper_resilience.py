"""Tests for reaper resilience: backoff, reinvoke, idle finalize, classify matrix."""
import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from lib import reaper


class TestBackoffDelayFor(unittest.TestCase):
    def test_first_retry(self):
        self.assertEqual(reaper._backoff_delay_for(1), 30)

    def test_second_retry(self):
        self.assertEqual(reaper._backoff_delay_for(2), 90)

    def test_third_retry(self):
        self.assertEqual(reaper._backoff_delay_for(3), 300)

    def test_fourth_retry(self):
        self.assertEqual(reaper._backoff_delay_for(4), 600)

    def test_caps_at_5(self):
        self.assertEqual(reaper._backoff_delay_for(5), 600)

    def test_caps_at_100(self):
        self.assertEqual(reaper._backoff_delay_for(100), 600)


def _kanban_task(status="testing", overall="inconclusive", finished_at=None,
                 test_run_count=1):
    return {
        "id": "T-9999",
        "status": status,
        "dispatch_payload": {
            "test_result": {
                "last_test_overall": overall,
                "last_test_finished_at": finished_at,
                "test_run_count": test_run_count,
            }
        }
    }


class TestNeedsTesterReinvoke(unittest.TestCase):
    def test_returns_false_when_status_not_testing(self):
        task = _kanban_task(status="done")
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_false_when_overall_pass(self):
        task = _kanban_task(overall="pass")
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_true_when_no_last_finished_at(self):
        # First chance — no record means re-invoke immediately
        task = _kanban_task(finished_at=None)
        self.assertTrue(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_false_when_backoff_window_active(self):
        # 10s ago, count=1 needs 30s
        recent = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=recent, test_run_count=1)
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_true_when_backoff_window_expired_count_1(self):
        # 35s ago, count=1 needs 30s — eligible
        elapsed = (datetime.now(timezone.utc) - timedelta(seconds=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=elapsed, test_run_count=1)
        self.assertTrue(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_false_when_backoff_count_2_window_active(self):
        # 60s ago, count=2 needs 90s
        recent = (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=recent, test_run_count=2)
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))

    def test_returns_true_when_backoff_count_2_window_expired(self):
        # 100s ago, count=2 needs 90s — eligible
        elapsed = (datetime.now(timezone.utc) - timedelta(seconds=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        task = _kanban_task(finished_at=elapsed, test_run_count=2)
        self.assertTrue(reaper._needs_tester_reinvoke(task, {}))

    def test_handles_malformed_finished_at_gracefully(self):
        task = _kanban_task(finished_at="not-a-timestamp", test_run_count=1)
        # Returns False (defensive — don't re-invoke if can't compute backoff)
        self.assertFalse(reaper._needs_tester_reinvoke(task, {}))


class TestClassifyExecutionWithKanban(unittest.TestCase):
    def test_already_reaped_when_no_kanban_task_passed(self):
        # Backwards compat: signature without kanban_task still works
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        self.assertEqual(reaper.classify_execution(status), "already_reaped")

    def test_already_reaped_when_kanban_task_done(self):
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        task = _kanban_task(status="done", overall="pass")
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "already_reaped")

    def test_needs_reinvoke_when_testing_inconclusive_backoff_expired(self):
        elapsed = (datetime.now(timezone.utc) - timedelta(seconds=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        task = _kanban_task(status="testing", overall="inconclusive",
                           finished_at=elapsed, test_run_count=1)
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "needs_reinvoke")

    def test_already_reaped_when_testing_inconclusive_backoff_active(self):
        recent = (datetime.now(timezone.utc) - timedelta(seconds=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": True}
        task = _kanban_task(status="testing", overall="inconclusive",
                           finished_at=recent, test_run_count=1)
        # Backoff window not expired — skip
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "already_reaped")

    def test_needs_lifecycle_unchanged_when_no_post_action(self):
        status = {"finished_at": "2026-04-29T10:00:00Z", "post_action_applied": False}
        task = _kanban_task(status="testing")
        self.assertEqual(reaper.classify_execution(status, kanban_task=task),
                         "needs_lifecycle")


class TestRunTickReinvokeBranch(unittest.TestCase):
    """Integration: full run_tick honoring needs_reinvoke."""

    def test_reinvoke_resets_post_action_and_records_stat(self):
        with tempfile.TemporaryDirectory() as td:
            execs_dir = Path(td) / "executions"
            execs_dir.mkdir()
            # Seed an execution.status.json: finished + post_action_applied=True
            status_file = execs_dir / "T-9999.status.json"
            status_file.write_text(json.dumps({
                "task_id": "T-9999",
                "session_id": "T-9999-x",
                "sprint_session_id": "sess-uuid",
                "started_at": "2026-04-29T09:00:00Z",
                "finished_at": "2026-04-29T10:00:00Z",
                "exit_code": 0,
                "post_action_applied": True,
                "pid": None,
                "run_mode": "detach",
            }))
            lockfile = Path(td) / "reaper.lock"

            # Mock kanban load (T-9999 is in 'testing' + inconclusive 35s ago)
            elapsed = (datetime.now(timezone.utc) - timedelta(seconds=35)).strftime("%Y-%m-%dT%H:%M:%SZ")
            fake_kanban = {"tasks": [{
                "id": "T-9999",
                "status": "testing",
                "project": "bevox-site",
                "dispatch_payload": {
                    "execution_session_id": "sess-uuid",
                    "test_result": {
                        "last_test_overall": "inconclusive",
                        "last_test_finished_at": elapsed,
                        "test_run_count": 1,
                    },
                },
            }]}

            with patch.object(reaper, "_load_kanban_state",
                              return_value=fake_kanban):
                result = reaper.run_tick(
                    trigger="test", dry_run=False,
                    executions_dir=execs_dir, lockfile=lockfile,
                )

            # Verify reinvoke counted in stats
            self.assertGreaterEqual(result.get("reinvoke_scheduled_count", 0), 1)

            # Verify post_action_applied was reset
            post = json.loads(status_file.read_text())
            self.assertFalse(post.get("post_action_applied"))

            # Verify action is recorded
            actions = result.get("actions_per_task", [])
            self.assertTrue(any(a.get("outcome") == "reinvoke_scheduled" for a in actions))


class TestDetectIdleFinalize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_jsonl(self, lines):
        p = Path(self.tmp) / "session.jsonl"
        with open(p, "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")
        return p

    def test_returns_false_when_path_none(self):
        self.assertFalse(reaper._detect_idle_finalize(None))

    def test_returns_false_when_file_missing(self):
        self.assertFalse(reaper._detect_idle_finalize(Path("/nonexistent/file.jsonl")))

    def test_returns_false_when_last_message_is_tool_use(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        p = self._write_jsonl([
            {"type": "assistant", "timestamp": old,
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
             ]}},
        ])
        # Tool_use means Claude still active — no idle finalize
        self.assertFalse(reaper._detect_idle_finalize(p))

    def test_returns_false_when_last_assistant_text_within_threshold(self):
        recent = (datetime.now(timezone.utc) - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        p = self._write_jsonl([
            {"type": "assistant", "timestamp": recent,
             "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]}},
        ])
        # 30s < 180s threshold — not idle yet
        self.assertFalse(reaper._detect_idle_finalize(p))

    def test_returns_true_when_last_assistant_text_idle_above_threshold(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        p = self._write_jsonl([
            {"type": "assistant", "timestamp": old,
             "message": {"role": "assistant", "content": [{"type": "text", "text": "Done"}]}},
        ])
        # 200s > 180s — Claude finalized + idle
        self.assertTrue(reaper._detect_idle_finalize(p))

    def test_returns_false_when_corrupt_lines_only(self):
        p = Path(self.tmp) / "session.jsonl"
        p.write_text("not json\nalso not json\n")
        self.assertFalse(reaper._detect_idle_finalize(p))

    def test_skips_corrupt_lines_uses_last_valid_assistant(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=200)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        p = Path(self.tmp) / "session.jsonl"
        with open(p, "w") as f:
            f.write(json.dumps({"type": "assistant", "timestamp": old,
                                "message": {"role": "assistant",
                                            "content": [{"type": "text", "text": "old"}]}}) + "\n")
            f.write("CORRUPT LINE\n")
        # Only valid line is old assistant text — should still detect idle
        self.assertTrue(reaper._detect_idle_finalize(p))


class TestIdleFinalizeAction(unittest.TestCase):
    def test_sigint_when_pid_responds(self):
        from unittest.mock import patch
        import signal
        sent_signals = []
        def fake_kill(pid, sig):
            sent_signals.append(sig)
            return None

        # _pid_alive will be called repeatedly; first True (initial check would
        # not happen because we go straight to SIGINT), then False after kill.
        # The implementation pattern: send SIGINT, then poll _pid_alive in a
        # loop. After SIGINT, fake_kill side-effect doesn't change _pid_alive
        # — we control that via the patch side_effect list.
        with patch.object(reaper, "_pid_alive", side_effect=[False, False, False]):
            with patch("os.kill", side_effect=fake_kill):
                with patch("time.sleep"):
                    reaper._idle_finalize_action("T-9999", {"pid": 12345})

        self.assertIn(signal.SIGINT, sent_signals)
        # Should NOT escalate to SIGTERM because _pid_alive returned False
        self.assertNotIn(signal.SIGTERM, sent_signals)

    def test_escalates_to_sigterm_then_sigkill(self):
        from unittest.mock import patch
        import signal
        sent = []
        def fake_kill(pid, sig):
            sent.append(sig)

        # Process never dies: _pid_alive always True
        with patch.object(reaper, "_pid_alive", return_value=True):
            with patch("os.kill", side_effect=fake_kill):
                with patch("time.sleep"):
                    reaper._idle_finalize_action("T-9999", {"pid": 12345})

        self.assertEqual(sent, [signal.SIGINT, signal.SIGTERM, signal.SIGKILL])

    def test_no_pid_returns_quietly(self):
        from unittest.mock import patch
        with patch("os.kill") as mock_kill:
            reaper._idle_finalize_action("T-9999", {"pid": None})
        mock_kill.assert_not_called()
