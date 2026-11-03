"""Tests migration script to schema_version 4 (split-and-migrate)."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _seed_v3_state(state_path: Path):
    """state.json v3 com sprint-4 órfã (project=None) tendo tasks de 2 projetos."""
    state = {
        "schema_version": 3,
        "generated_at": "2026-04-24T00:00:00Z",
        "last_event_seq": 10,
        "projects": ["bevox-mobile", "bevox-backend"],
        "sprints": [
            {
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T15:36:25Z",
                "closed_at": None, "created_by": "bernard"
            }
        ],
        "tasks": [
            # ativa de bevox-mobile
            {"id": "T-100", "title": "active mobile", "status": "ready",
             "sprint_id": "sprint-4", "project": "bevox-mobile",
             "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
             "dispatch_payload": {}},
            # ativa de bevox-backend
            {"id": "T-101", "title": "active backend", "status": "in_progress",
             "sprint_id": "sprint-4", "project": "bevox-backend",
             "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
             "dispatch_payload": {}},
            # terminal — fica em sprint-4
            {"id": "T-102", "title": "archived", "status": "archived",
             "sprint_id": "sprint-4", "project": "bevox-mobile",
             "blocked": False, "updated_at": "2026-04-20T00:00:00Z",
             "dispatch_payload": {}},
        ],
    }
    state_path.write_text(json.dumps(state))


class TestMigrateHappyPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n  - bevox-backend\n")
        _seed_v3_state(self.tmp_state)
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

    def test_migrate_creates_per_project_sprints(self):
        from lib import migration
        result = migration.migrate_to_per_project(actor="test")
        self.assertTrue(result["ok"])
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["schema_version"], 4)
        # Cada projeto tem current+next
        active_by_proj = {}
        for sp in state["sprints"]:
            if sp["state"] in ("current", "next"):
                active_by_proj.setdefault(sp.get("project"), []).append(sp["state"])
        self.assertEqual(sorted(active_by_proj.keys()),
                         ["bevox-backend", "bevox-mobile"])
        for proj, states in active_by_proj.items():
            self.assertEqual(sorted(states), ["current", "next"])

    def test_migrate_ignores_terminal_tasks_in_orphan_sprint(self):
        from lib import migration
        migration.migrate_to_per_project(actor="test")
        state = json.loads(self.tmp_state.read_text())
        # T-102 (archived) ficou em sprint-4
        t102 = next(t for t in state["tasks"] if t["id"] == "T-102")
        self.assertEqual(t102["sprint_id"], "sprint-4")
        # T-100 (ativa mobile) e T-101 (ativa backend) re-sprintadas
        t100 = next(t for t in state["tasks"] if t["id"] == "T-100")
        t101 = next(t for t in state["tasks"] if t["id"] == "T-101")
        # ambas devem estar em current de seu projeto
        sprints = {sp["id"]: sp for sp in state["sprints"]}
        self.assertEqual(sprints[t100["sprint_id"]]["project"], "bevox-mobile")
        self.assertEqual(sprints[t100["sprint_id"]]["state"], "current")
        self.assertEqual(sprints[t101["sprint_id"]]["project"], "bevox-backend")
        self.assertEqual(sprints[t101["sprint_id"]]["state"], "current")

    def test_migrate_idempotent_on_v4_schema(self):
        from lib import migration
        migration.migrate_to_per_project(actor="test")
        result2 = migration.migrate_to_per_project(actor="test")
        self.assertTrue(result2["ok"])
        self.assertTrue(result2.get("noop", False))
        self.assertEqual(result2.get("reason"), "already_migrated")

    def test_migrate_dry_run_outputs_plan_no_mutation(self):
        from lib import migration
        result = migration.migrate_to_per_project(actor="test", dry_run=True)
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        # plano deve mostrar tasks a re-sprintar
        self.assertIn("would_resprint", result)
        self.assertEqual(len(result["would_resprint"]), 2)  # T-100 + T-101
        # state.json intocado
        state = json.loads(self.tmp_state.read_text())
        self.assertEqual(state["schema_version"], 3)


class TestMigrateErrorCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        from lib import store
        self.tmp_state = Path(self.tmp) / "state.json"
        self.tmp_events = Path(self.tmp) / "events.jsonl"
        self.tmp_projects = Path(self.tmp) / "projects.yml"
        self.tmp_projects.write_text("projects:\n  - bevox-mobile\n")
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

    def test_migrate_fails_on_task_missing_project(self):
        # state v3 com task ativa project=None
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-200", "title": "no project", "status": "ready",
                "sprint_id": "sprint-4", "project": None,
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        with self.assertRaises(ValueError) as ctx:
            migration.migrate_to_per_project(actor="test")
        self.assertIn("TASK_MISSING_PROJECT", str(ctx.exception))
        # state.json não mutou
        post = json.loads(self.tmp_state.read_text())
        self.assertEqual(post["schema_version"], 3)

    def test_migrate_fails_on_unknown_project(self):
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-201", "title": "unknown proj", "status": "ready",
                "sprint_id": "sprint-4", "project": "wat",
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        with self.assertRaises(ValueError) as ctx:
            migration.migrate_to_per_project(actor="test")
        self.assertIn("TASK_UNKNOWN_PROJECT", str(ctx.exception))
        post = json.loads(self.tmp_state.read_text())
        self.assertEqual(post["schema_version"], 3)

    def test_migrate_creates_backup_before_mutation(self):
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-300", "title": "ok", "status": "ready",
                "sprint_id": "sprint-4", "project": "bevox-mobile",
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        result = migration.migrate_to_per_project(actor="test")
        self.assertTrue(result["ok"])
        backup = self.tmp_state.with_suffix(".pre-schema-v4.bak")
        self.assertTrue(backup.exists())
        # backup tem schema antigo (v3)
        backed = json.loads(backup.read_text())
        self.assertEqual(backed["schema_version"], 3)

    def test_migrate_emits_audit_events(self):
        state = {
            "schema_version": 3, "generated_at": "2026-04-24T00:00:00Z",
            "last_event_seq": 0, "projects": ["bevox-mobile"],
            "sprints": [{
                "id": "sprint-4", "name": "Sprint 4", "state": "current",
                "project": None, "created_at": "2026-04-18T00:00:00Z",
                "closed_at": None, "created_by": "test",
            }],
            "tasks": [{
                "id": "T-400", "title": "ok", "status": "ready",
                "sprint_id": "sprint-4", "project": "bevox-mobile",
                "blocked": False, "updated_at": "2026-04-24T00:00:00Z",
                "dispatch_payload": {},
            }],
        }
        self.tmp_state.write_text(json.dumps(state))
        from lib import migration
        migration.migrate_to_per_project(actor="test")
        # events.jsonl deve ter sprint_created, task_resprinted, sprint_closed, schema_migrated
        events_text = self.tmp_events.read_text()
        types = []
        for line in events_text.splitlines():
            if line.strip():
                types.append(json.loads(line)["type"])
        self.assertIn("sprint_created", types)
        self.assertIn("task_resprinted", types)
        self.assertIn("sprint_closed", types)
        self.assertIn("schema_migrated", types)


if __name__ == "__main__":
    unittest.main()
