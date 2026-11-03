"""Test F1: has_open_escalation_for_project filtra task IDs por status ativo
antes do scan de escalation files.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F1
"""
import unittest
import tempfile
import shutil
from pathlib import Path

from lib.cron import has_open_escalation_for_project


class TestActiveStatusFilter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.clr_dir = self.tmpdir / "clarification" / "escalations"
        self.tester_dir = self.tmpdir / "tester" / "escalations"
        self.clr_dir.mkdir(parents=True)
        self.tester_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_clr_file(self, task_id: str):
        (self.clr_dir / f"{task_id}-clr-1.md").write_text("---\nstatus: open\n---\n")

    def test_done_task_with_clr_file_does_not_block(self):
        """Task done com clr file órfão NÃO bloqueia projeto."""
        self._create_clr_file("T-0161")
        tasks = [{"id": "T-0161", "status": "done"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_archived_task_with_clr_file_does_not_block(self):
        self._create_clr_file("T-0070")
        tasks = [{"id": "T-0070", "status": "archived"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_rejected_task_with_clr_file_does_not_block(self):
        self._create_clr_file("T-0049")
        tasks = [{"id": "T-0049", "status": "rejected"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_backlog_task_with_clr_file_does_not_block(self):
        self._create_clr_file("T-0150")
        tasks = [{"id": "T-0150", "status": "backlog"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_ready_task_with_clr_file_blocks(self):
        """Task ready com clr file pendente DEVE bloquear (gate ativo)."""
        self._create_clr_file("T-0165")
        tasks = [{"id": "T-0165", "status": "ready"}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_in_progress_task_with_tr_file_blocks(self):
        (self.tester_dir / "T-0050-tr-1.md").write_text("---\n---\n")
        tasks = [{"id": "T-0050", "status": "in_progress"}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_testing_task_with_clr_file_blocks(self):
        self._create_clr_file("T-0024")
        tasks = [{"id": "T-0024", "status": "testing"}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_blocked_flag_overrides_status(self):
        """Task com blocked=true SEMPRE conta (mesmo se status=backlog)."""
        self._create_clr_file("T-0150")
        tasks = [{"id": "T-0150", "status": "backlog", "blocked": True}]
        self.assertTrue(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_no_active_tasks_returns_false_immediately(self):
        """Lista sem tasks ativas retorna False sem scan de filesystem."""
        tasks = [{"id": "T-0001", "status": "done"}, {"id": "T-0002", "status": "archived"}]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))

    def test_mixed_project_only_active_count(self):
        """Done com file + Ready sem file → False (filter funciona)."""
        self._create_clr_file("T-DONE")
        tasks = [
            {"id": "T-DONE", "status": "done"},
            {"id": "T-READY", "status": "ready"},
        ]
        self.assertFalse(has_open_escalation_for_project(tasks, self.clr_dir, self.tester_dir))


if __name__ == "__main__":
    unittest.main()
