"""Tests sprint per-project schema (v4): find_sprint/get_current/get_next."""
import unittest
from typing import Any, Dict


def _make_state(*sprints) -> Dict[str, Any]:
    return {
        "schema_version": 4,
        "generated_at": "2026-04-25T00:00:00Z",
        "last_event_seq": 0,
        "projects": ["bevox-mobile", "bevox-backend"],
        "sprints": list(sprints),
        "tasks": [],
    }


def _sp(seq: int, st: str, project: str) -> Dict[str, Any]:
    return {
        "id": f"sprint-{seq}",
        "name": f"Sprint {seq}",
        "state": st,
        "project": project,
        "created_at": "2026-04-25T00:00:00Z",
        "closed_at": None,
        "created_by": "test",
    }


class TestFindSprintPerProject(unittest.TestCase):
    def test_find_sprint_current_requires_project_arg(self):
        from lib import sprint
        state = _make_state(_sp(1, "current", "bevox-mobile"))
        with self.assertRaises(ValueError) as ctx:
            sprint.find_sprint(state, "current")
        self.assertIn("project required", str(ctx.exception).lower())

    def test_find_sprint_current_per_project_returns_correct(self):
        from lib import sprint
        state = _make_state(
            _sp(1, "current", "bevox-mobile"),
            _sp(2, "current", "bevox-backend"),
            _sp(3, "next", "bevox-mobile"),
        )
        sp_mob = sprint.find_sprint(state, "current", project="bevox-mobile")
        self.assertEqual(sp_mob["id"], "sprint-1")
        sp_bac = sprint.find_sprint(state, "current", project="bevox-backend")
        self.assertEqual(sp_bac["id"], "sprint-2")

    def test_find_sprint_literal_id_works_without_project(self):
        from lib import sprint
        state = _make_state(_sp(7, "current", "bevox-mobile"))
        sp = sprint.find_sprint(state, "sprint-7")
        self.assertEqual(sp["id"], "sprint-7")


import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestBootstrap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text(
            "projects:\n  - bevox-mobile\n  - bevox-backend\n  - openclaw\n"
        )
        # initial empty state
        self.tmp_state.write_text(
            '{"schema_version": 4, "generated_at": "2026-04-25T00:00:00Z",'
            ' "last_event_seq": 0, "projects": ["bevox-mobile","bevox-backend","openclaw"],'
            ' "sprints": [], "tasks": []}'
        )
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

    def test_bootstrap_creates_for_each_projects_yml_entry(self):
        from lib import sprint
        result = sprint.bootstrap(actor="test")
        self.assertTrue(result["ok"])
        # 3 projects × (current+next) = 6 sprints
        import json
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(len(state["sprints"]), 6)
        by_project = {}
        for sp in state["sprints"]:
            by_project.setdefault(sp["project"], []).append(sp["state"])
        self.assertEqual(sorted(by_project.keys()),
                         ["bevox-backend", "bevox-mobile", "openclaw"])
        for proj, states in by_project.items():
            self.assertEqual(sorted(states), ["current", "next"])

    def test_bootstrap_idempotent_skips_existing(self):
        from lib import sprint
        sprint.bootstrap(actor="test")
        # second run is noop pra projetos já bootstrapados
        result2 = sprint.bootstrap(actor="test")
        self.assertTrue(result2["ok"])
        # still 6 sprints
        import json
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(len(state["sprints"]), 6)
        self.assertEqual(result2.get("created", []), [])

    def test_bootstrap_dry_run_does_not_mutate(self):
        from lib import sprint
        result = sprint.bootstrap(actor="test", dry_run=True)
        self.assertTrue(result["ok"])
        self.assertIn("would_create", result)
        self.assertEqual(len(result["would_create"]), 6)  # 3 projects × 2 sprints
        # state.json intocado (sprints vazio)
        import json
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["sprints"], [])


class TestCloseCurrentPerProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n  - bevox-backend\n")
        # state com current+next pra 2 projetos + 1 task em current[bevox-mobile]
        import json
        state = {
            "schema_version": 4,
            "generated_at": "2026-04-25T00:00:00Z",
            "last_event_seq": 4,
            "projects": ["bevox-mobile", "bevox-backend"],
            "sprints": [
                _sp(1, "current", "bevox-mobile"),
                _sp(2, "next", "bevox-mobile"),
                _sp(3, "current", "bevox-backend"),
                _sp(4, "next", "bevox-backend"),
            ],
            "tasks": [
                {"id": "T-A", "title": "A", "status": "ready",
                 "sprint_id": "sprint-1", "project": "bevox-mobile",
                 "blocked": False, "updated_at": "2026-04-25T00:00:00Z",
                 "dispatch_payload": {}},
            ],
        }
        self.tmp_state.write_text(json.dumps(state))
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

    def test_close_current_only_affects_target_project(self):
        from lib import sprint
        result = sprint.close_current(
            carryover=[{"task_id": "T-A", "action": "move_current"}],
            actor="test",
            project="bevox-mobile",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["closed"], "sprint-1")
        # bevox-backend intocado
        import json
        state = json.loads(self.tmp_state.read_text())
        bb_sprints = [sp for sp in state["sprints"] if sp["project"] == "bevox-backend"]
        bb_states = sorted([sp["state"] for sp in bb_sprints])
        self.assertEqual(bb_states, ["current", "next"])

    def test_close_current_creates_new_next_for_project(self):
        from lib import sprint
        sprint.close_current(
            carryover=[{"task_id": "T-A", "action": "move_current"}],
            actor="test",
            project="bevox-mobile",
        )
        import json
        state = json.loads(self.tmp_state.read_text())
        mob_sprints = [sp for sp in state["sprints"] if sp["project"] == "bevox-mobile"]
        states = sorted([sp["state"] for sp in mob_sprints])
        self.assertEqual(states, ["closed", "current", "next"])

    def test_close_current_carryover_propagates_correctly(self):
        from lib import sprint
        sprint.close_current(
            carryover=[{"task_id": "T-A", "action": "move_current"}],
            actor="test",
            project="bevox-mobile",
        )
        import json
        state = json.loads(self.tmp_state.read_text())
        # task T-A devia estar agora no novo current de bevox-mobile (sprint-2 promovido)
        ta = next(t for t in state["tasks"] if t["id"] == "T-A")
        # sprint-2 era next de bevox-mobile, virou current após close
        self.assertEqual(ta["sprint_id"], "sprint-2")


class TestTaskSprintInvariants(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n  - bevox-backend\n")
        import json
        state = {
            "schema_version": 4,
            "generated_at": "2026-04-25T00:00:00Z",
            "last_event_seq": 0,
            "projects": ["bevox-mobile", "bevox-backend"],
            "sprints": [
                _sp(1, "current", "bevox-mobile"),
                _sp(2, "next", "bevox-mobile"),
                _sp(3, "current", "bevox-backend"),
                _sp(4, "next", "bevox-backend"),
            ],
            "tasks": [],
        }
        self.tmp_state.write_text(json.dumps(state))
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

    def test_task_sprint_project_consistency_enforced(self):
        """task add com sprint_id de outro projeto → INVALID_SPRINT_PROJECT_MISMATCH."""
        from lib import task
        # tenta criar task de bevox-mobile com sprint literal sprint-3 (de bevox-backend)
        with self.assertRaises(ValueError) as ctx:
            task.create(
                title="bad",
                payload={"goal": "x", "acceptance_criteria": ["x"], "spec_ref": "n/a"},
                actor="test",
                sprint="sprint-3",
                project="bevox-mobile",
            )
        self.assertIn("INVALID_SPRINT_PROJECT_MISMATCH", str(ctx.exception))

    def test_get_current_returns_none_when_project_has_no_current(self):
        from lib import sprint as sprint_lib, store
        state = store.read_state()
        # remove bevox-mobile current
        state["sprints"] = [sp for sp in state["sprints"]
                            if not (sp["state"] == "current" and sp["project"] == "bevox-mobile")]
        import json
        self.tmp_state.write_text(json.dumps(state))
        # re-read e check
        state = store.read_state()
        result = sprint_lib.get_current(state, project="bevox-mobile")
        self.assertIsNone(result)

    def test_resolve_sprint_id_alias_requires_project(self):
        from lib import task
        from lib import store
        state = store.read_state()
        # alias sem project → ValueError
        with self.assertRaises(ValueError):
            task._resolve_sprint_id(state, "current")
        # alias com project → sprint_id
        sid = task._resolve_sprint_id(state, "current", project="bevox-mobile")
        self.assertEqual(sid, "sprint-1")


if __name__ == "__main__":
    unittest.main()
