"""Testes end-to-end cmd_task_add com gate ativo (wave-4)."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


CLI = os.path.expanduser("~/.openclaw/kanban-tasks/cli.sh")


def _seed_state(tmp_dir):
    seed = {
        "schema_version": 4,
        "projects": ["openclaw"],
        "sprints": [{
            "id": "sprint-1", "state": "current",
            "start_date": "2026-04-21", "end_date": "2026-04-27",
            "name": "test", "project": "openclaw",
            "created_at": "2026-04-21T00:00:00Z",
            "closed_at": None,
            "created_by": "test",
        }],
        "tasks": [],
        "last_event_seq": 0,
    }
    (tmp_dir / "state.json").write_text(json.dumps(seed))
    (tmp_dir / "events.jsonl").write_text("")


class TestCmdTaskAddGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kanban-cli-test-"))
        _seed_state(self.tmp)
        self.env = {**os.environ, "KANBAN_ROOT": str(self.tmp)}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _run(self, *args):
        return subprocess.run(
            [CLI, *args], env=self.env,
            capture_output=True, text=True, timeout=10,
        )

    def test_add_without_payload_arg_errors(self):
        """argparse required=True -> missing --payload -> exit 2 (argparse) ou 1."""
        r = self._run("task", "add", "x", "--project", "openclaw", "--json")
        self.assertNotEqual(r.returncode, 0)
        # argparse default error exit is 2; but may be 1 if caught
        combined = (r.stderr + r.stdout).lower()
        self.assertIn("payload", combined)

    def test_add_with_empty_payload_rejected_by_gate(self):
        r = self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", "{}", "--json",
        )
        self.assertEqual(r.returncode, 1, f"stdout={r.stdout} stderr={r.stderr}")
        parsed = json.loads(r.stdout)
        self.assertFalse(parsed["ok"])
        self.assertEqual(parsed["code"], "PAYLOAD_INCOMPLETE")

    def test_add_with_invalid_json_payload_errors(self):
        r = self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", "not json", "--json",
        )
        self.assertEqual(r.returncode, 1)
        parsed = json.loads(r.stdout)
        self.assertFalse(parsed["ok"])
        self.assertIn("json", parsed["error"].lower())

    def test_add_with_complete_payload_succeeds(self):
        payload = {
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["AC1: runs"],
        }
        r = self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", json.dumps(payload), "--json",
        )
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr}")
        parsed = json.loads(r.stdout)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["task"]["dispatch_payload"], payload)

    def test_add_rejection_emits_audit_event(self):
        self._run(
            "task", "add", "x", "--project", "openclaw",
            "--payload", "{}", "--json",
        )
        events_text = (self.tmp / "events.jsonl").read_text()
        lines = events_text.splitlines()
        reject_events = [
            json.loads(l) for l in lines
            if json.loads(l).get("type") == "task_creation_rejected_payload_incomplete"
        ]
        self.assertEqual(len(reject_events), 1)
        evt = reject_events[0]
        self.assertIn("missing_fields", evt)
        self.assertIn("spec_ref", evt["missing_fields"])
        self.assertIn("acceptance_criteria", evt["missing_fields"])
        self.assertEqual(evt.get("attempted_title"), "x")
        self.assertEqual(evt.get("source"), "cli")


if __name__ == "__main__":
    unittest.main()
