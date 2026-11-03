"""Tests for ubn_actions CLI entrypoint (cli.sh ubn ...).

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §6.2
"""
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from lib import ubn_actions


class TestCLIEntry(unittest.TestCase):
    """Test main() argparse dispatch."""

    def test_done_subcommand_invokes_force_done(self):
        with patch.object(ubn_actions, "force_done") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            result = ubn_actions.main(["done", "T-0200", "--reason", "manual"])
            self.assertEqual(result, 0)
            mock.assert_called_once_with("T-0200", "via-telegram", "manual")

    def test_reject_subcommand_invokes_force_reject(self):
        with patch.object(ubn_actions, "force_reject") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            result = ubn_actions.main(["reject", "T-0201", "--reason", "ruim"])
            self.assertEqual(result, 0)
            mock.assert_called_once_with("T-0201", "via-telegram", "ruim")

    def test_answer_subcommand_invokes_manual_answer(self):
        with patch.object(ubn_actions, "manual_answer") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            result = ubn_actions.main(["answer", "T-0202", "--text", "minha resposta"])
            self.assertEqual(result, 0)
            mock.assert_called_once_with("T-0202", "minha resposta")

    def test_retry_subcommand_looks_up_task_and_dispatches(self):
        task_data = {
            "task": {
                "id": "T-0203",
                "status": "in_progress",
                "blocked_reason": "test_failed: AC X",
            }
        }
        with patch("lib.ubn_actions.subprocess.run") as mock_run:
            with patch.object(ubn_actions, "_kanban") as mock_kanban:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout=json.dumps(task_data), stderr=""
                )
                mock_kanban.return_value = {"task": {"id": "T-0203"}}
                result = ubn_actions.main(["retry", "T-0203"])
                self.assertEqual(result, 0)
                # Verify kanban was called for unblock and move operations
                self.assertGreater(mock_kanban.call_count, 0)

    def test_backfill_override_with_stale_tasks(self):
        with patch.object(ubn_actions, "backfill_override") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            result = ubn_actions.main(
                ["backfill", "--override", "--stale", "T-0100,T-0101"]
            )
            self.assertEqual(result, 0)
            mock.assert_called_once_with(["T-0100", "T-0101"], [])

    def test_backfill_override_with_renotify_tasks(self):
        with patch.object(ubn_actions, "backfill_override") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            result = ubn_actions.main(
                ["backfill", "--override", "--renotify", "T-0102,T-0103"]
            )
            self.assertEqual(result, 0)
            mock.assert_called_once_with([], ["T-0102", "T-0103"])

    def test_backfill_override_with_both_stale_and_renotify(self):
        with patch.object(ubn_actions, "backfill_override") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            result = ubn_actions.main(
                [
                    "backfill",
                    "--override",
                    "--stale",
                    "T-0100,T-0101",
                    "--renotify",
                    "T-0102",
                ]
            )
            self.assertEqual(result, 0)
            mock.assert_called_once_with(["T-0100", "T-0101"], ["T-0102"])

    def test_list_subcommand_returns_open_escalations(self):
        import tempfile

        tmp = tempfile.mkdtemp()
        escalations_dir = Path(tmp)
        (escalations_dir / "T-0300-blk-1.md").write_text("---\nstatus: open\n---\n")
        (escalations_dir / "T-0300-blk-2.md").write_text("---\nstatus: resolved\n---\n")
        (escalations_dir / "T-0301-blk-1.md").write_text("---\nstatus: open\n---\n")

        with patch.object(ubn_actions, "UBN_ESCALATIONS_DIR", escalations_dir):
            result = ubn_actions.main(["list"])
        self.assertEqual(result, 0)

        import shutil

        shutil.rmtree(tmp, ignore_errors=True)

    def test_done_with_no_reason_uses_default(self):
        with patch.object(ubn_actions, "force_done") as mock:
            mock.return_value = ubn_actions.ActionResult(summary="ok")
            result = ubn_actions.main(["done", "T-0205"])
            self.assertEqual(result, 0)
            mock.assert_called_once_with("T-0205", "via-telegram", "(no reason)")

    def test_done_failure_returns_1(self):
        with patch.object(ubn_actions, "force_done") as mock:
            mock.return_value = ubn_actions.ActionResult(
                summary="failed", success=False
            )
            result = ubn_actions.main(["done", "T-0206"])
            self.assertEqual(result, 1)

    def test_answer_requires_text_argument(self):
        # This test verifies argparse rejects answer without --text
        with self.assertRaises(SystemExit):
            ubn_actions.main(["answer", "T-0207"])


if __name__ == "__main__":
    unittest.main()
