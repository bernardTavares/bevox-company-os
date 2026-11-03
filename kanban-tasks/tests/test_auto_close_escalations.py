"""Test F2: _auto_close_escalations fecha files relacionadas quando task
move pra terminal status.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-04-ubn-w2-loop-self-healing.md §F2
"""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib.task import _auto_close_escalations


class TestAutoCloseEscalations(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.clr_esc = self.tmpdir / "clarification-agent" / "escalations"
        self.tester_esc = self.tmpdir / "tester-agent" / "escalations"
        self.clr_esc.mkdir(parents=True)
        self.tester_esc.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _patch_dirs(self):
        return patch.multiple(
            "lib.task",
            UBN_CLR_ESCALATIONS_DIR=self.clr_esc,
            TESTER_ESCALATIONS_DIR=self.tester_esc,
        )

    def test_ubn_blk_frontmatter_status_rewritten(self):
        """File T-0070-blk-1.md com status:open vira status:closed_task_resolved."""
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text(
            "---\n"
            "task_id: T-0070\n"
            "status: open\n"
            "criterion: blocked\n"
            "---\n\n"
            "# body\n",
            encoding="utf-8",
        )
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            with patch("lib.store.append_event"):
                with patch("lib.store.next_seq", return_value=1):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00:00Z"):
                        result = _auto_close_escalations(state, "T-0070", "done", "bernard")

        new_text = path.read_text(encoding="utf-8")
        self.assertIn("status: closed_task_resolved", new_text)
        self.assertNotIn("status: open", new_text)
        # Body preserved
        self.assertIn("# body", new_text)
        self.assertEqual(len(result["affected_files"]), 1)
        self.assertEqual(result["affected_files"][0]["action"], "frontmatter_closed")

    def test_ubn_blk_already_closed_idempotent(self):
        """Re-run em file já closed = noop (não quebra)."""
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text(
            "---\n"
            "task_id: T-0070\n"
            "status: closed_task_resolved\n"
            "---\n",
            encoding="utf-8",
        )
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            with patch("lib.store.append_event"):
                with patch("lib.store.next_seq", return_value=1):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00:00Z"):
                        result = _auto_close_escalations(state, "T-0070", "done", "bernard")
        self.assertEqual(len(result["affected_files"]), 0)

    def test_clr_file_in_escalations_moved_to_resolved(self):
        """T-XXXX-clr-N.md em clr/escalations/ é movido pra _resolved-YYYYMMDD/."""
        path = self.clr_esc / "T-0161-clr-1.md"
        path.write_text("# orphan clr file\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            with patch("lib.store.append_event"):
                with patch("lib.store.next_seq", return_value=1):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00:00Z"):
                        result = _auto_close_escalations(state, "T-0161", "done", "bernard")

        # Original gone
        self.assertFalse(path.exists())
        # Moved to _resolved-YYYYMMDD/
        resolved_dirs = list(self.clr_esc.glob("_resolved-*"))
        self.assertEqual(len(resolved_dirs), 1)
        moved = resolved_dirs[0] / "T-0161-clr-1.md"
        self.assertTrue(moved.exists())
        self.assertEqual(result["affected_files"][0]["action"], "moved_to_resolved")

    def test_tr_file_in_tester_moved_to_resolved(self):
        path = self.tester_esc / "T-0050-tr-2.md"
        path.write_text("# orphan tr\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            with patch("lib.store.append_event"):
                with patch("lib.store.next_seq", return_value=1):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00:00Z"):
                        result = _auto_close_escalations(state, "T-0050", "rejected", "bernard")

        self.assertFalse(path.exists())
        resolved_dirs = list(self.tester_esc.glob("_resolved-*"))
        self.assertEqual(len(resolved_dirs), 1)
        self.assertTrue((resolved_dirs[0] / "T-0050-tr-2.md").exists())

    def test_question_files_not_moved(self):
        """Question files em questions/ NÃO devem ser tocados (history)."""
        questions_dir = self.tmpdir / "clarification-agent" / "questions"
        questions_dir.mkdir(parents=True)
        q_path = questions_dir / "T-0161-clr-1.md"
        q_path.write_text("# question\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            with patch("lib.store.append_event"):
                with patch("lib.store.next_seq", return_value=1):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00:00Z"):
                        _auto_close_escalations(state, "T-0161", "done", "bernard")
        self.assertTrue(q_path.exists())  # preserved

    def test_archived_status_triggers_hook(self):
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text("---\nstatus: open\n---\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            with patch("lib.store.append_event"):
                with patch("lib.store.next_seq", return_value=1):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00:00Z"):
                        result = _auto_close_escalations(state, "T-0070", "archived", "bernard")
        self.assertEqual(len(result["affected_files"]), 1)

    def test_non_terminal_status_noop(self):
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text("---\nstatus: open\n---\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            result = _auto_close_escalations(state, "T-0070", "in_progress", "bernard")
        self.assertEqual(len(result["affected_files"]), 0)
        self.assertEqual(path.read_text(encoding="utf-8"), "---\nstatus: open\n---\n")

    def test_event_emitted_on_change(self):
        path = self.clr_esc / "T-0070-blk-1.md"
        path.write_text("---\ntask_id: T-0070\nstatus: open\n---\n", encoding="utf-8")
        state = {"events": [], "last_event_seq": 5}
        with self._patch_dirs():
            with patch("lib.store.append_event") as mock_append:
                with patch("lib.store.next_seq", return_value=6):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00Z"):
                        _auto_close_escalations(state, "T-0070", "done", "bernard")
        mock_append.assert_called_once()
        event = mock_append.call_args[0][0]
        self.assertEqual(event["type"], "task_escalations_auto_closed")
        self.assertEqual(event["payload"]["task_id"], "T-0070")
        self.assertEqual(event["payload"]["new_status"], "done")

    def test_move_collision_uses_numeric_suffix(self):
        """Se file destino já existe (mesmo dia), backfill suffix-2."""
        # Pre-create _resolved-YYYYMMDD/ with same filename
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        resolved = self.clr_esc / f"_resolved-{today}"
        resolved.mkdir()
        (resolved / "T-0161-clr-1.md").write_text("first version", encoding="utf-8")

        # Now create new orphan with same name
        path = self.clr_esc / "T-0161-clr-1.md"
        path.write_text("second version", encoding="utf-8")

        state = {"events": [], "last_event_seq": 0}
        with self._patch_dirs():
            with patch("lib.store.append_event"):
                with patch("lib.store.next_seq", return_value=1):
                    with patch("lib.store.now_iso", return_value="2026-05-04T12:00Z"):
                        result = _auto_close_escalations(state, "T-0161", "done", "bernard")

        # Original gone
        self.assertFalse(path.exists())
        # First version preserved
        self.assertEqual(
            (resolved / "T-0161-clr-1.md").read_text(encoding="utf-8"),
            "first version",
        )
        # Second moved with suffix
        self.assertTrue((resolved / "T-0161-clr-1-2.md").exists())
        self.assertEqual(
            (resolved / "T-0161-clr-1-2.md").read_text(encoding="utf-8"),
            "second version",
        )


class TestArchiveTriggersHook(unittest.TestCase):
    """archive() é code-path separado de move_status; precisa hook próprio."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.clr_esc = self.tmpdir / "clarification-agent" / "escalations"
        self.clr_esc.mkdir(parents=True)
        self.path = self.clr_esc / "T-9999-blk-1.md"
        self.path.write_text(
            "---\ntask_id: T-9999\nstatus: open\n---\n", encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_archive_calls_auto_close(self):
        """archive() chama _auto_close_escalations com status='archived'."""
        from lib import task as task_mod
        with patch.object(task_mod, "UBN_CLR_ESCALATIONS_DIR", self.clr_esc):
            with patch.object(task_mod, "_auto_close_escalations") as mock_hook:
                state = {
                    "tasks": [{"id": "T-9999", "status": "done", "project": "test"}],
                    "events": [], "last_event_seq": 0,
                }
                with patch("lib.store.mutate_state") as mock_mutate:
                    cm = MagicMock()
                    cm.__enter__.return_value = state
                    cm.__exit__.return_value = False
                    mock_mutate.return_value = cm
                    with patch("lib.store.next_seq", return_value=1):
                        with patch("lib.store.now_iso", return_value="2026-05-04T12:00Z"):
                            with patch("lib.store.append_event"):
                                task_mod.archive("T-9999", actor="bernard")
                mock_hook.assert_called_once_with(state, "T-9999", "archived", "bernard")


if __name__ == "__main__":
    unittest.main()
