"""Tests sprint.set_session_id / clear_session_id (wave dispatcher-same-session-per-sprint)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _seed_state(state_path: Path, sprints):
    state_path.write_text(json.dumps({
        "schema_version": 4,
        "generated_at": "2026-04-25T12:00:00Z",
        "last_event_seq": 0,
        "projects": ["test-project"],
        "sprints": sprints,
        "tasks": [],
    }))


def _sp(seq, st, project, session_id=None):
    sp = {
        "id": f"sprint-{seq}",
        "name": f"Sprint {seq}",
        "state": st,
        "project": project,
        "created_at": "2026-04-25T00:00:00Z",
        "closed_at": None,
        "created_by": "test",
    }
    if session_id is not None:
        sp["execution_session_id"] = session_id
    return sp


class TestSetSessionId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - test-project\n")
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
            patch.object(store, "ROOT", Path(self.tmp)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_set_session_id_on_active_sprint_persists(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project")])
        from lib import sprint
        result = sprint.set_session_id("sprint-1", "abc-123-uuid", actor="test")
        self.assertTrue(result["ok"])
        self.assertFalse(result.get("noop", False))
        self.assertEqual(result["session_id"], "abc-123-uuid")
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["sprints"][0]["execution_session_id"], "abc-123-uuid")
        events = [json.loads(l) for l in self.tmp_events.read_text().splitlines() if l.strip()]
        self.assertEqual(events[-1]["type"], "sprint_session_id_set")
        self.assertEqual(events[-1]["session_id"], "abc-123-uuid")

    def test_set_session_id_idempotent_returns_existing(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project", session_id="existing-uuid")])
        from lib import sprint
        result = sprint.set_session_id("sprint-1", "new-attempt-uuid", actor="test")
        self.assertTrue(result["ok"])
        self.assertTrue(result["noop"])
        self.assertEqual(result["existing"], "existing-uuid")
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["sprints"][0]["execution_session_id"], "existing-uuid")

    def test_set_session_id_on_closed_sprint_raises(self):
        _seed_state(self.tmp_state, [_sp(1, "closed", "test-project")])
        from lib import sprint
        with self.assertRaises(ValueError) as ctx:
            sprint.set_session_id("sprint-1", "abc-uuid", actor="test")
        self.assertIn("closed", str(ctx.exception).lower())

    def test_set_session_id_unknown_sprint_raises(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project")])
        from lib import sprint
        with self.assertRaises(ValueError) as ctx:
            sprint.set_session_id("sprint-99", "abc-uuid", actor="test")
        self.assertIn("not found", str(ctx.exception).lower())


class TestClearSessionId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - test-project\n")
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
            patch.object(store, "ROOT", Path(self.tmp)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_clear_session_id_on_active_sprint(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project", session_id="abc-uuid")])
        from lib import sprint
        result = sprint.clear_session_id("sprint-1", actor="bernard", reason="test")
        self.assertTrue(result["ok"])
        self.assertFalse(result.get("noop", False))
        self.assertEqual(result["cleared"], "abc-uuid")
        state = json.loads(self.tmp_state.read_text())
        self.assertIsNone(state["sprints"][0]["execution_session_id"])
        events = [json.loads(l) for l in self.tmp_events.read_text().splitlines() if l.strip()]
        self.assertEqual(events[-1]["type"], "sprint_session_id_cleared")
        self.assertEqual(events[-1]["previous_session_id"], "abc-uuid")
        self.assertEqual(events[-1]["reason"], "test")

    def test_clear_session_id_idempotent(self):
        _seed_state(self.tmp_state, [_sp(1, "current", "test-project")])  # no session_id
        from lib import sprint
        result = sprint.clear_session_id("sprint-1", actor="bernard")
        self.assertTrue(result["ok"])
        self.assertTrue(result["noop"])

    def test_clear_session_id_on_closed_sprint_raises(self):
        _seed_state(self.tmp_state, [_sp(1, "closed", "test-project", session_id="abc")])
        from lib import sprint
        with self.assertRaises(ValueError) as ctx:
            sprint.clear_session_id("sprint-1", actor="bernard")
        self.assertIn("closed", str(ctx.exception).lower())


class TestCloseCurrentDoesNotMigrateSession(unittest.TestCase):
    """Regression: close_current promove next->current sem migrar session_id (lazy semantics)."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - test-project\n")
        # current com session_id, next sem
        _seed_state(self.tmp_state, [
            _sp(1, "current", "test-project", session_id="current-uuid"),
            _sp(2, "next", "test-project"),
        ])
        self.patches = [
            patch.object(store, "STATE_PATH", self.tmp_state),
            patch.object(store, "EVENTS_PATH", self.tmp_events),
            patch.object(store, "PROJECTS_PATH", self.tmp_projects),
            patch.object(store, "ROOT", Path(self.tmp)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp)

    def test_close_current_does_not_migrate_session_id(self):
        from lib import sprint
        result = sprint.close_current(carryover=[], actor="bernard", project="test-project")
        self.assertTrue(result["ok"])
        state = json.loads(self.tmp_state.read_text())
        sprints_by_id = {sp["id"]: sp for sp in state["sprints"]}
        # sprint-1 (closed) preservou session_id
        self.assertEqual(sprints_by_id["sprint-1"]["state"], "closed")
        self.assertEqual(sprints_by_id["sprint-1"]["execution_session_id"], "current-uuid")
        # sprint-2 (promoted to current) NAO tem session_id (or null)
        self.assertEqual(sprints_by_id["sprint-2"]["state"], "current")
        self.assertIsNone(sprints_by_id["sprint-2"].get("execution_session_id"))


if __name__ == "__main__":
    unittest.main()
