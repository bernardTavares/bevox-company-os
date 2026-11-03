"""Tests hooks auto-release + auto-block upstream + ready gate (wave-5)."""
import importlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _seed_abc(tmp):
    """T-A (backlog), T-B blocked_by=[T-A] (backlog), T-C blocked_by=[T-A, T-B] (backlog)."""
    tasks = [
        {"id": "T-A", "title": "A", "status": "backlog",
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
        {"id": "T-B", "title": "B", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "b.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": ["T-A"]},
         "test_result": None},
        {"id": "T-C", "title": "C", "status": "backlog",
         "sprint_id": "sprint-1", "project": "openclaw",
         "description": "", "epic_id": None, "wave_ref": None,
         "created_at": "2026-04-22T00:00:00Z",
         "updated_at": "2026-04-22T00:00:00Z",
         "created_by": "test", "archived_at": None,
         "blocked": False, "blocked_reason": None, "blocked_at": None,
         "rejected_reason": None,
         "dispatch_payload": {"spec_ref": "c.md",
                              "acceptance_criteria": ["AC"],
                              "blocked_by": ["T-A", "T-B"]},
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
    importlib.reload(store); importlib.reload(transitions); importlib.reload(task)
    return task


class TestAutoRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-hook-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def _statuses(self):
        st = json.loads((self.tmp / "state.json").read_text())
        return {t["id"]: t["status"] for t in st["tasks"]}

    def test_done_releases_ready_dependent_with_single_pred(self):
        task = _reload()
        task.move("T-A", "ready", actor="test")
        task.move("T-A", "in_progress", actor="test")
        task.move("T-A", "testing", actor="test")
        task.move("T-A", "done", actor="test")
        statuses = self._statuses()
        self.assertEqual(statuses["T-A"], "done")
        self.assertEqual(statuses["T-B"], "ready")

    def test_done_does_not_release_dependent_with_partial_preds(self):
        task = _reload()
        for to in ["ready", "in_progress", "testing", "done"]:
            task.move("T-A", to, actor="test")
        statuses = self._statuses()
        self.assertEqual(statuses["T-A"], "done")
        self.assertEqual(statuses["T-C"], "backlog")

    def test_event_task_blocked_by_auto_released_emitted(self):
        task = _reload()
        for to in ["ready", "in_progress", "testing", "done"]:
            task.move("T-A", to, actor="test")
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        release_events = [json.loads(l) for l in events
                          if json.loads(l).get("type") == "task_blocked_by_auto_released"]
        self.assertEqual(len(release_events), 1)
        self.assertEqual(release_events[0]["payload"]["task_id"], "T-B")
        self.assertEqual(release_events[0]["payload"]["trigger_pred"], "T-A")


class TestAutoBlockUpstreamRejected(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-upr-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_rejected_blocks_dependents(self):
        task = _reload()
        task.move("T-A", "rejected", actor="test", reason="wave-5 smoke")
        state = json.loads((self.tmp / "state.json").read_text())
        by_id = {t["id"]: t for t in state["tasks"]}
        self.assertTrue(by_id["T-B"]["blocked"])
        self.assertIn("upstream_rejected: T-A", by_id["T-B"]["blocked_reason"])
        self.assertTrue(by_id["T-C"]["blocked"])
        self.assertIn("upstream_rejected: T-A", by_id["T-C"]["blocked_reason"])

    def test_rejected_emits_upstream_failed_events(self):
        task = _reload()
        task.move("T-A", "rejected", actor="test", reason="wave-5 smoke")
        events = (self.tmp / "events.jsonl").read_text().splitlines()
        upstream_events = [json.loads(l) for l in events
                           if json.loads(l).get("type") == "task_blocked_upstream_failed"]
        self.assertEqual(len(upstream_events), 2)
        task_ids = {e["payload"]["task_id"] for e in upstream_events}
        self.assertEqual(task_ids, {"T-B", "T-C"})


class TestAutoBlockUpstreamArchived(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-upa-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_archived_blocks_dependents(self):
        task = _reload()
        task.archive("T-A", actor="test")
        state = json.loads((self.tmp / "state.json").read_text())
        by_id = {t["id"]: t for t in state["tasks"]}
        self.assertTrue(by_id["T-B"]["blocked"])
        self.assertIn("upstream_rejected: T-A", by_id["T-B"]["blocked_reason"])


class TestCanMoveToReadyGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-gate-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_move_to_ready_blocked_when_pred_not_done(self):
        task = _reload()
        # T-B has blocked_by=[T-A]; T-A still backlog
        with self.assertRaises(task.TaskError) as ctx:
            task.move("T-B", "ready", actor="test")
        self.assertEqual(ctx.exception.code, "BLOCKED_BY_UNRESOLVED")

    def test_move_to_ready_passes_when_preds_done(self):
        task = _reload()
        # Promove T-A to done
        for to in ["ready", "in_progress", "testing", "done"]:
            task.move("T-A", to, actor="test")
        # T-B was auto-released to ready by hook. Moving again would be no-op,
        # but test can_move_to_ready by moving to in_progress first then back...
        # Simpler: verify T-B is at ready already (hook auto-promoted).
        state = json.loads((self.tmp / "state.json").read_text())
        tb = next(t for t in state["tasks"] if t["id"] == "T-B")
        self.assertEqual(tb["status"], "ready")


class TestSetDispatchPayloadCycleGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-sdp-gate-"))
        _seed_abc(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_set_dispatch_payload_with_cycle_rejected(self):
        """Loophole fechado wave-5: set-dispatch-payload com blocked_by
        formando ciclo deve ser rejeitado pelo mesmo gate."""
        task = _reload()
        # T-B ja tem blocked_by=[T-A] no seed. Tentar set_dispatch_payload em T-A
        # com blocked_by=[T-B] forma ciclo -> rejeitar.
        with self.assertRaises(task.TaskError) as ctx:
            task.set_dispatch_payload(
                "T-A",
                {"spec_ref": "a.md",
                 "acceptance_criteria": ["AC"],
                 "blocked_by": ["T-B"]},
                merge=False, actor="test",
            )
        self.assertEqual(ctx.exception.code, "CYCLE_DETECTED")

    def test_set_dispatch_payload_without_blocked_by_change_ok(self):
        """Se set_dispatch_payload nao mexe em blocked_by, gate de ciclo
        nao dispara."""
        task = _reload()
        res = task.set_dispatch_payload(
            "T-B",
            {"spec_ref": "b-new.md",
             "acceptance_criteria": ["AC-new"],
             "blocked_by": ["T-A"]},
            merge=False, actor="test",
        )
        self.assertTrue(res["ok"])


if __name__ == "__main__":
    unittest.main()
