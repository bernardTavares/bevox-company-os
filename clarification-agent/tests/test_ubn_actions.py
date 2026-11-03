"""Unit tests for UBN actions canonical Python.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6
"""
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from lib import ubn_actions


class TestSmartRetryMatrix(unittest.TestCase):
    def test_test_failed_in_progress_routes_to_move_testing(self):
        action = ubn_actions._select_retry_action("test_failed: AC X", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_testing")

    def test_test_inconclusive_in_progress_routes_to_move_testing(self):
        action = ubn_actions._select_retry_action("test_inconclusive: timeout", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_testing")

    def test_clarification_escalation_routes_to_move_ready(self):
        action = ubn_actions._select_retry_action(
            "clarification_escalation_required: drafter timeout", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_ready")

    def test_stuck_in_testing_routes_to_invoke_tester_direct(self):
        action = ubn_actions._select_retry_action("stuck-in-testing >30min", "testing")
        self.assertEqual(action.__name__, "retry_invoke_tester_direct")

    def test_branch_checkout_failed_in_progress_routes_to_move_ready(self):
        action = ubn_actions._select_retry_action(
            "branch_checkout_failed: dirty", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_ready")

    def test_branch_checkout_failed_ready_routes_to_noop_wait_cron(self):
        action = ubn_actions._select_retry_action(
            "branch_checkout_failed: dirty", "ready")
        self.assertEqual(action.__name__, "retry_noop_wait_cron")

    def test_unknown_pattern_falls_back_to_move_ready(self):
        action = ubn_actions._select_retry_action("totally_new_block_reason", "in_progress")
        self.assertEqual(action.__name__, "retry_move_to_ready")


class TestForceActions(unittest.TestCase):
    def test_force_done_invokes_kanban_move_with_force(self):
        with patch.object(ubn_actions, "_kanban") as mock_k:
            mock_k.return_value = {"task": {"id": "T-0080", "status": "done"}}
            result = ubn_actions.force_done("T-0080", "esc-1", "validei manual")
        self.assertTrue(result.success)
        self.assertEqual(mock_k.call_count, 2)
        move_args = mock_k.call_args_list[1].args[0]
        self.assertIn("--force", move_args)
        self.assertIn("done", move_args)

    def test_force_reject_invokes_kanban_move_with_force(self):
        with patch.object(ubn_actions, "_kanban") as mock_k:
            mock_k.return_value = {"task": {"id": "T-0081", "status": "rejected"}}
            result = ubn_actions.force_reject("T-0081", "esc-1", "task inviável")
        self.assertTrue(result.success)
        move_args = mock_k.call_args_list[1].args[0]
        self.assertIn("rejected", move_args)


class TestManualAnswer(unittest.TestCase):
    def test_returns_audit_only_when_no_open_question(self):
        with patch.object(ubn_actions, "_find_latest_open_question",
                          return_value=None):
            result = ubn_actions.manual_answer("T-0090", "minha resposta")
        self.assertIn("audit only", result.summary)
        self.assertTrue(result.success)


class TestBackfillOverride(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.escalations_dir = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_marks_stale_creates_minimal_escalation_files(self):
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            ubn_actions.backfill_override(
                stale_task_ids=["T-0006", "T-0008"],
                renotify_task_ids=[],
            )
        files = sorted(self.escalations_dir.glob("*.md"))
        names = [f.name for f in files]
        self.assertIn("T-0006-blk-1.md", names)
        self.assertIn("T-0008-blk-1.md", names)
        for f in files:
            content = f.read_text()
            self.assertIn("status: stale", content)

    def test_marks_renotify_creates_open_escalation_files(self):
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            ubn_actions.backfill_override(stale_task_ids=[],
                                          renotify_task_ids=["T-0161"])
        files = list(self.escalations_dir.glob("T-0161-*.md"))
        self.assertEqual(len(files), 1)
        content = files[0].read_text()
        self.assertIn("status: open", content)


class TestFindEscalation(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.escalations_dir = Path(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_find_open_escalation_for_task(self):
        (self.escalations_dir / "T-0100-blk-1.md").write_text("---\nstatus: open\n---\n")
        (self.escalations_dir / "T-0100-blk-2.md").write_text("---\nstatus: resolved\n---\n")
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            result = ubn_actions.find_open_escalation_for_task("T-0100")
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "T-0100-blk-1.md")

    def test_returns_none_when_no_open(self):
        (self.escalations_dir / "T-0101-blk-1.md").write_text("---\nstatus: resolved\n---\n")
        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", self.escalations_dir):
            result = ubn_actions.find_open_escalation_for_task("T-0101")
        self.assertIsNone(result)
