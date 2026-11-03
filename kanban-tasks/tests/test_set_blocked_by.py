"""Tests set_blocked_by: central write-path com cycle gate (wave-5)."""
import importlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _seed(tmp, tasks_override=None):
    tasks = tasks_override or [
        {"id": "T-0001", "title": "A", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "x.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": []},
         "test_result": None},
        {"id": "T-0002", "title": "B", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "y.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": []},
         "test_result": None},
    ]
    seed = {
        "schema_version": 3,
        "projects": ["openclaw"],
        "sprints": [{"id": "sprint-1", "state": "current",
                     "start_date": "2026-04-21", "end_date": "2026-04-27",
                     "name": "test"}],
        "tasks": tasks,
        "last_event_seq": 0,
    }
    (tmp / "state.json").write_text(json.dumps(seed))
    (tmp / "events.jsonl").write_text("")


def _reload():
    from lib import store, transitions, task
    importlib.reload(store)
    importlib.reload(transitions)
    importlib.reload(task)
    return task


class TestSetBlockedBy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-setbb-"))
        _seed(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_replace_preds_persists(self):
        task = _reload()
        res = task.set_blocked_by("T-0002", ["T-0001"], actor="test")
        self.assertTrue(res["ok"])
        self.assertEqual(res["task"]["dispatch_payload"]["blocked_by"],
                         ["T-0001"])
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        set_events = [json.loads(l) for l in events
                      if json.loads(l).get("type") == "task_blocked_by_set"]
        self.assertEqual(len(set_events), 1)
        self.assertEqual(set_events[0]["payload"]["preds"], ["T-0001"])
        self.assertEqual(set_events[0]["payload"]["previous_preds"], [])

    def test_self_cycle_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-0001", ["T-0001"], actor="test")
        self.assertEqual(ctx.exception.code, "CYCLE_DETECTED")

    def test_pred_not_found_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-0001", ["T-9999"], actor="test")
        self.assertEqual(ctx.exception.code, "PRED_NOT_FOUND")
        state = json.loads((self.tmp / "state.json").read_text())
        t1 = next(t for t in state["tasks"] if t["id"] == "T-0001")
        self.assertEqual(t1["dispatch_payload"]["blocked_by"], [])

    def test_task_not_found_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-9999", ["T-0001"], actor="test")
        self.assertEqual(ctx.exception.code, "TASK_NOT_FOUND")

    def test_invalid_format_string_rejected(self):
        task = _reload()
        with self.assertRaises(task.TaskError) as ctx:
            task.set_blocked_by("T-0001", "T-0002", actor="test")
        self.assertEqual(ctx.exception.code, "BLOCKED_BY_INVALID")

    def test_event_carries_previous_preds_on_replace(self):
        task = _reload()
        task.set_blocked_by("T-0002", ["T-0001"], actor="test")
        task.set_blocked_by("T-0002", [], actor="test")
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        set_events = [json.loads(l) for l in events
                      if json.loads(l).get("type") == "task_blocked_by_set"]
        self.assertEqual(len(set_events), 2)
        self.assertEqual(set_events[1]["payload"]["previous_preds"], ["T-0001"])
        self.assertEqual(set_events[1]["payload"]["preds"], [])


if __name__ == "__main__":
    unittest.main()
