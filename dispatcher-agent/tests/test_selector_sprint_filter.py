"""Tests dispatcher selector com sprint filter (per-project) + kill-switch."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _seed_state(state_path: Path, *, current_sprint_for_proj=None,
                tasks=None):
    """Cria state.json mínimo. Default: sem current pra teste de no-current."""
    sprints = []
    if current_sprint_for_proj:
        for proj, sid in current_sprint_for_proj.items():
            sprints.append({
                "id": sid, "name": f"Sprint X", "state": "current",
                "project": proj, "created_at": "2026-04-25T00:00:00Z",
                "closed_at": None, "created_by": "test",
            })
    state_path.write_text(json.dumps({
        "schema_version": 4,
        "sprints": sprints,
        "tasks": tasks or [],
    }))


class TestSelectorSprintFilter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import selector
        self.state_path = Path(self.tmp) / "state.json"
        self.patcher = patch.object(selector, "KANBAN_STATE", self.state_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmp)
        os.environ.pop("OPENCLAW_DISPATCHER_IGNORE_SPRINT", None)

    def test_selector_filters_by_current_sprint(self):
        """Tasks ready em current sprint dispatchadas; em next sprint ignoradas."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-1", "title": "in current", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
                {"id": "T-2", "title": "in next", "status": "ready",
                 "sprint_id": "sprint-8", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-1")

    def test_selector_kill_switch_disables_filter(self):
        """OPENCLAW_DISPATCHER_IGNORE_SPRINT=1 → ignora filtro, retorna ready de qualquer sprint."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-OUT", "title": "fora do sprint", "status": "ready",
                 "sprint_id": "sprint-99", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ])
        os.environ["OPENCLAW_DISPATCHER_IGNORE_SPRINT"] = "1"
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-OUT")

    def test_selector_no_current_sprint_raises(self):
        """Projeto sem current sprint → SelectorError NO_CURRENT_SPRINT."""
        _seed_state(self.state_path,
            current_sprint_for_proj=None,  # ninguém tem current
            tasks=[
                {"id": "T-X", "title": "lonely", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        with self.assertRaises(selector.SelectorError) as ctx:
            selector.select_next_ready("test-project")
        self.assertEqual(ctx.exception.code, "NO_CURRENT_SPRINT")

    def test_selector_respects_blocked_flag(self):
        """Task em current sprint mas blocked=True → ignorada."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-B", "title": "blocked", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": True, "created_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
                {"id": "T-OK", "title": "ok", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T00:01:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-OK")

    def test_selector_returns_oldest_first(self):
        """Ordering por created_at ascendente preservada."""
        _seed_state(self.state_path,
            current_sprint_for_proj={"test-project": "sprint-7"},
            tasks=[
                {"id": "T-NEW", "title": "newer", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T10:00:00Z",
                 "dispatch_payload": {}},
                {"id": "T-OLD", "title": "older", "status": "ready",
                 "sprint_id": "sprint-7", "project": "test-project",
                 "blocked": False, "created_at": "2026-04-25T08:00:00Z",
                 "dispatch_payload": {}},
            ])
        from lib import selector
        result = selector.select_next_ready("test-project")
        self.assertEqual(result["id"], "T-OLD")


class TestCronSkippedNoCurrentSprint(unittest.TestCase):
    """Testa que process_projects contabiliza skipped_no_current_sprint corretamente."""

    def test_process_projects_skipped_no_current_sprint_outcome(self):
        """dispatch_one_fn retornando skipped_no_current_sprint → stats corretos."""
        import tempfile
        import shutil
        from lib import cron

        tmp = tempfile.mkdtemp()
        try:
            # Stub: dispatch_one_fn sempre retorna NO_CURRENT_SPRINT
            def mock_dispatch_one(project, dry_run=False):
                return {
                    "outcome": "skipped_no_current_sprint",
                    "task_id": None,
                    "skip_reason": "NO_CURRENT_SPRINT",
                }

            # Stub: check_blocks nunca bloqueia
            def mock_check_blocks(project):
                return (False, "")

            stats = cron.process_projects(
                opted_in=["test-project"],
                dry_run=False,
                dispatch_one_fn=mock_dispatch_one,
                check_blocks_fn=mock_check_blocks,
            )

            self.assertEqual(stats["projects_skipped_no_current_sprint"], 1)
            self.assertEqual(stats["dispatched_count"], 0)
            self.assertEqual(len(stats["actions_per_project"]), 1)
            action = stats["actions_per_project"][0]
            self.assertEqual(action["outcome"], "skipped_no_current_sprint")
            self.assertEqual(action["project"], "test-project")
            self.assertIsNone(action["task_id"])
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
