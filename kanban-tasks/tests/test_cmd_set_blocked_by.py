"""Tests CLI task set-blocked-by (wave-5)."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


CLI = os.path.expanduser("~/.openclaw/kanban-tasks/cli.sh")


def _seed_two_tasks(tmp):
    tasks = [
        {"id": "T-0001", "title": "A", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "a.md",
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
         "dispatch_payload": {"spec_ref": "b.md",
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
        "tasks": tasks, "last_event_seq": 0,
    }
    (tmp / "state.json").write_text(json.dumps(seed))
    (tmp / "events.jsonl").write_text("")


class TestCmdSetBlockedBy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-cli-sbb-"))
        _seed_two_tasks(self.tmp)
        self.env = {**os.environ, "KANBAN_ROOT": str(self.tmp)}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, *args):
        return subprocess.run([CLI, *args], env=self.env,
                              capture_output=True, text=True, timeout=10)

    def test_preds_replaces(self):
        r = self._run("task", "set-blocked-by", "T-0002", "--preds", "T-0001",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 0, f"stderr: {r.stderr}")
        state = json.loads((self.tmp / "state.json").read_text())
        t2 = next(t for t in state["tasks"] if t["id"] == "T-0002")
        self.assertEqual(t2["dispatch_payload"]["blocked_by"], ["T-0001"])

    def test_add_appends(self):
        # First set T-0002 with [T-0001]
        self._run("task", "set-blocked-by", "T-0002", "--preds", "T-0001",
                  "--actor", "test", "--json")
        # Add T-0001 again - idempotent (no-op)
        r = self._run("task", "set-blocked-by", "T-0002", "--add", "T-0001",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 0)
        state = json.loads((self.tmp / "state.json").read_text())
        t2 = next(t for t in state["tasks"] if t["id"] == "T-0002")
        self.assertEqual(t2["dispatch_payload"]["blocked_by"], ["T-0001"])

    def test_remove_deletes_pred(self):
        self._run("task", "set-blocked-by", "T-0002", "--preds", "T-0001",
                  "--actor", "test", "--json")
        r = self._run("task", "set-blocked-by", "T-0002", "--remove", "T-0001",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 0)
        state = json.loads((self.tmp / "state.json").read_text())
        t2 = next(t for t in state["tasks"] if t["id"] == "T-0002")
        self.assertEqual(t2["dispatch_payload"]["blocked_by"], [])

    def test_self_cycle_exit_1(self):
        r = self._run("task", "set-blocked-by", "T-0001", "--preds", "T-0001",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 1)
        parsed = json.loads(r.stdout)
        self.assertEqual(parsed["code"], "CYCLE_DETECTED")

    def test_pred_not_found_exit_1(self):
        r = self._run("task", "set-blocked-by", "T-0001", "--preds", "T-9999",
                      "--actor", "test", "--json")
        self.assertEqual(r.returncode, 1)
        parsed = json.loads(r.stdout)
        self.assertEqual(parsed["code"], "PRED_NOT_FOUND")

    def test_preds_and_add_mutually_exclusive(self):
        r = self._run("task", "set-blocked-by", "T-0001",
                      "--preds", "T-0002", "--add", "T-0003",
                      "--actor", "test", "--json")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
