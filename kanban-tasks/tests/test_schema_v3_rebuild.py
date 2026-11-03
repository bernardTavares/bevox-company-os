"""Tests schema v3 bump + rebuild populates blocked_by default (wave-5)."""
import importlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


def _seed_v2_state(tmp):
    """Seed state.json v2 com tasks sem blocked_by em dispatch_payload."""
    seed = {
        "schema_version": 2,
        "projects": ["openclaw"],
        "sprints": [{"id": "sprint-1", "state": "current",
                     "start_date": "2026-04-21", "end_date": "2026-04-27",
                     "name": "test"}],
        "tasks": [
            {
                "id": "T-0001", "title": "legacy", "status": "backlog",
                "sprint_id": "sprint-1", "project": "openclaw",
                "description": "", "epic_id": None, "wave_ref": None,
                "created_at": "2026-04-21T00:00:00Z",
                "updated_at": "2026-04-21T00:00:00Z",
                "created_by": "test", "archived_at": None,
                "blocked": False, "blocked_reason": None, "blocked_at": None,
                "rejected_reason": None,
                "dispatch_payload": {"spec_ref": "x.md",
                                      "acceptance_criteria": ["AC"]},
                "test_result": None,
            },
            {
                "id": "T-0002", "title": "no payload", "status": "backlog",
                "sprint_id": "sprint-1", "project": "openclaw",
                "description": "", "epic_id": None, "wave_ref": None,
                "created_at": "2026-04-21T00:00:00Z",
                "updated_at": "2026-04-21T00:00:00Z",
                "created_by": "test", "archived_at": None,
                "blocked": False, "blocked_reason": None, "blocked_at": None,
                "rejected_reason": None, "dispatch_payload": None,
                "test_result": None,
            },
        ],
        "last_event_seq": 0,
    }
    (tmp / "state.json").write_text(json.dumps(seed))
    (tmp / "events.jsonl").write_text("")


def _reload_store():
    from lib import store as store_mod
    importlib.reload(store_mod)
    return store_mod


class TestSchemaV3EmptyState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-schema-"))
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def test_empty_state_uses_v4(self):
        store = _reload_store()
        empty = store._empty_state()
        self.assertEqual(empty["schema_version"], 4)


class TestRebuildPopulatesBlockedByDefault(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kb-rebuild-"))
        _seed_v2_state(self.tmp)
        self._orig = os.environ.get("KANBAN_ROOT")
        os.environ["KANBAN_ROOT"] = str(self.tmp)

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("KANBAN_ROOT", None)
        else:
            os.environ["KANBAN_ROOT"] = self._orig
        shutil.rmtree(self.tmp)

    def _run_rebuild_cli(self):
        CLI = os.path.expanduser("~/.openclaw/kanban-tasks/cli.sh")
        r = subprocess.run([CLI, "rebuild", "--json"],
                           env={**os.environ}, capture_output=True, text=True,
                           timeout=10)
        return r

    def test_rebuild_adds_blocked_by_default_to_existing_tasks(self):
        r = self._run_rebuild_cli()
        self.assertEqual(r.returncode, 0, f"stderr: {r.stderr}")
        state = json.loads((self.tmp / "state.json").read_text())
        self.assertEqual(state["schema_version"], 3)
        for t in state["tasks"]:
            dp = t.get("dispatch_payload") or {}
            self.assertIn("blocked_by", dp,
                          f"task {t['id']} sem blocked_by default")
            self.assertIsInstance(dp["blocked_by"], list)
            self.assertEqual(dp["blocked_by"], [])


if __name__ == "__main__":
    unittest.main()
