"""Tests for notifier-state.json schema v2 helpers."""
import json
import tempfile
import unittest
from pathlib import Path

from lib import store


class TestSchemaV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.tmp.close()
        self.path = Path(self.tmp.name)

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()

    def test_load_state_v2_returns_empty_when_missing(self):
        self.path.unlink()
        result = store.load_state_v2(self.path)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["notifications"], {})

    def test_save_state_v2_writes_atomic(self):
        state = {
            "schema_version": 2,
            "heartbeat_at": "2026-04-28T14:00:00Z",
            "notifications": {
                "T-0001-clr-1": {
                    "task_id": "T-0001",
                    "project": "bevox-site",
                    "token_alias": "project-bevox-site",
                    "chat_id": "-100123456",
                    "thread_id": 18,
                    "telegram_message_id": 273,
                    "sent_at": "2026-04-28T11:36:01Z",
                    "status": "pending",
                    "resolved_at": None,
                    "resolved_via": None,
                }
            }
        }
        store.save_state_v2(self.path, state)
        loaded = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["schema_version"], 2)
        self.assertEqual(loaded["notifications"]["T-0001-clr-1"]["status"], "pending")

    def test_load_state_v2_preserves_v1_schema_version_field(self):
        # v1 schema (current production)
        v1 = {
            "schema_version": 1,
            "heartbeat_at": "2026-04-28T14:00:00Z",
            "notifications": {
                "T-0024-clr-4": {
                    "task_id": "T-0024",
                    "notified_at": "2026-04-27T14:33:42Z",
                    "telegram_message_id": 273,
                    "source_path": "/path/to/escalation.md",
                }
            }
        }
        self.path.write_text(json.dumps(v1))
        result = store.load_state_v2(self.path)
        # load_state_v2 NEVER mutates schema by itself — caller calls migrate
        self.assertEqual(result["schema_version"], 1)

    def test_load_state_v2_returns_empty_v2_on_corrupt_json(self):
        self.path.write_text("not valid json {{{")
        result = store.load_state_v2(self.path)
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["notifications"], {})

    def test_save_state_v2_does_not_mutate_caller_state(self):
        state = {"notifications": {}}
        store.save_state_v2(self.path, state)
        self.assertNotIn("schema_version", state)


class TestMigrationV1V2(unittest.TestCase):
    def test_migrate_marks_unresolvable_as_orphan(self):
        v1 = {
            "schema_version": 1,
            "notifications": {
                "T-0024-clr-4": {
                    "task_id": "T-0024",
                    "notified_at": "2026-04-27T14:33:42Z",
                    "telegram_message_id": 273,
                    "source_path": "/path/to/escalation.md",
                }
            }
        }
        # Empty resolver = nothing can be resolved
        def resolver(task_id):
            return None
        result = store.migrate_v1_to_v2(v1, resolver)
        entry = result["notifications"]["T-0024-clr-4"]
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(entry["status"], "orphan")
        self.assertEqual(entry["telegram_message_id"], 273)
        self.assertIsNone(entry.get("project"))
        self.assertEqual(entry["sent_at"], "2026-04-27T14:33:42Z")

    def test_migrate_resolves_when_meta_available(self):
        v1 = {
            "schema_version": 1,
            "notifications": {
                "T-0105-clr-1": {
                    "task_id": "T-0105",
                    "notified_at": "2026-04-28T11:36:01Z",
                    "telegram_message_id": 273,
                }
            }
        }
        def resolver(task_id):
            if task_id == "T-0105":
                return {
                    "project": "bevox-site",
                    "token_alias": "project-bevox-site",
                    "chat_id": "-100xxxxx",
                    "thread_id": 18,
                }
            return None
        result = store.migrate_v1_to_v2(v1, resolver)
        entry = result["notifications"]["T-0105-clr-1"]
        self.assertEqual(entry["status"], "pending")
        self.assertEqual(entry["project"], "bevox-site")
        self.assertEqual(entry["token_alias"], "project-bevox-site")
        self.assertEqual(entry["thread_id"], 18)
        self.assertEqual(entry["telegram_message_id"], 273)

    def test_migrate_idempotent_on_v2_input(self):
        v2 = {
            "schema_version": 2,
            "notifications": {
                "T-0001-clr-1": {
                    "task_id": "T-0001",
                    "status": "pending",
                    "project": "bevox-site",
                }
            }
        }
        def resolver(task_id):
            return None
        result = store.migrate_v1_to_v2(v2, resolver)
        self.assertEqual(result, v2)


if __name__ == "__main__":
    unittest.main()
