"""Testes task_lib.create() com kwarg payload novo (wave-4)."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path


def _seed_state(tmp_dir):
    """Gera state.json minimo viavel em tmp_dir."""
    seed = {
        "schema_version": 4,
        "projects": ["openclaw"],
        "sprints": [{
            "id": "sprint-1",
            "name": "Sprint 1",
            "state": "current",
            "project": "openclaw",
            "created_at": "2026-04-21T00:00:00Z",
            "closed_at": None,
            "created_by": "test",
        }],
        "tasks": [],
        "last_event_seq": 0,
    }
    (tmp_dir / "state.json").write_text(json.dumps(seed))
    (tmp_dir / "events.jsonl").write_text("")


def _reload_modules():
    """Reload store + task apos env KANBAN_ROOT setado."""
    import importlib
    from lib import store as store_mod
    from lib import task as task_mod
    importlib.reload(store_mod)
    importlib.reload(task_mod)
    return task_mod


class TestTaskCreateWithPayload(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kanban-test-create-"))
        _seed_state(self.tmp)
        self._orig_root = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig_root is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig_root
        shutil.rmtree(self.tmp)

    def test_create_with_payload_persists_dispatch_payload(self):
        task_mod = _reload_modules()
        payload = {
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["AC1: runs"],
        }
        res = task_mod.create(
            title="test task", sprint="current", project="openclaw",
            payload=payload, actor="test",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["task"]["dispatch_payload"], payload)

    def test_create_without_payload_kwarg_sets_dispatch_none(self):
        """Backward compat: chamadas sem payload continuam com None.
        Gate NAO eh invocado em create() — gate eh responsabilidade do caller
        (cmd_task_add + route.ts). Separation of concerns."""
        task_mod = _reload_modules()
        res = task_mod.create(
            title="blank", sprint="current", project="openclaw", actor="test",
        )
        self.assertTrue(res["ok"])
        self.assertIsNone(res["task"]["dispatch_payload"])

    def test_create_event_task_created_includes_payload_keys(self):
        task_mod = _reload_modules()
        payload = {
            "spec_ref": "35_specs/y.md",
            "acceptance_criteria": ["AC1"],
        }
        task_mod.create(
            title="t", sprint="current", project="openclaw",
            payload=payload, actor="test",
        )
        events_lines = (self.tmp / "events.jsonl").read_text().splitlines()
        created_evt = None
        for line in events_lines:
            e = json.loads(line)
            if e.get("type") == "task_created":
                created_evt = e
                break
        self.assertIsNotNone(created_evt)
        self.assertIn("payload_keys", created_evt)
        self.assertIn("spec_ref", created_evt["payload_keys"])
        self.assertIn("acceptance_criteria", created_evt["payload_keys"])


if __name__ == "__main__":
    unittest.main()
