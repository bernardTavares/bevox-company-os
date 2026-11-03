"""Tests for event envelope, writer, reader, and actor validation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent


class TestEventEnvelope(unittest.TestCase):
    def test_make_event_has_required_fields(self):
        evt = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"})
        self.assertIn("ts", evt)
        self.assertIn("event_id", evt)
        self.assertEqual(evt["actor"], "cli")
        self.assertEqual(evt["type"], "spec.activated")
        self.assertEqual(evt["payload"]["spec_path"], "x.md")
        self.assertTrue(evt["event_id"].startswith("evt_"))

    def test_event_ids_are_unique(self):
        a = agent.make_event(actor="cli", type="spec.activated", payload={})
        b = agent.make_event(actor="cli", type="spec.activated", payload={})
        self.assertNotEqual(a["event_id"], b["event_id"])

    def test_ts_is_iso_utc(self):
        evt = agent.make_event(actor="cli", type="spec.activated", payload={})
        # Should end in Z (UTC) and parse as ISO
        self.assertTrue(evt["ts"].endswith("Z"))


class TestActorValidation(unittest.TestCase):
    def test_cli_can_emit_spec_activated(self):
        # Should not raise
        agent.validate_actor("cli", "spec.activated")

    def test_agent_can_emit_task_proposed(self):
        agent.validate_actor("delivery-agent", "task.proposed")

    def test_agent_cannot_emit_task_created(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("delivery-agent", "task.created")

    def test_cli_cannot_emit_task_proposed(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("cli", "task.proposed")

    def test_unknown_actor_rejected(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("bernard", "spec.activated")

    def test_unknown_type_rejected(self):
        with self.assertRaises(agent.ActorError):
            agent.validate_actor("cli", "made.up.event")


class TestEventWriterReader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        self.tmp.close()
        self.path = Path(self.tmp.name)
        self.path.unlink()  # start empty / nonexistent

    def tearDown(self):
        if self.path.exists():
            self.path.unlink()

    def test_emit_writes_one_line(self):
        agent.emit_event_to(self.path, actor="cli", type="spec.activated", payload={"spec_path": "x.md"})
        lines = self.path.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(parsed["type"], "spec.activated")

    def test_emit_appends_multiple(self):
        agent.emit_event_to(self.path, actor="cli", type="spec.activated", payload={"spec_path": "a.md"})
        agent.emit_event_to(self.path, actor="cli", type="spec.activated", payload={"spec_path": "b.md"})
        lines = self.path.read_text().splitlines()
        self.assertEqual(len(lines), 2)

    def test_emit_rejects_invalid_actor(self):
        with self.assertRaises(agent.ActorError):
            agent.emit_event_to(self.path, actor="delivery-agent", type="spec.activated", payload={"spec_path": "x.md"})

    def test_iter_events_yields_each_line(self):
        agent.emit_event_to(self.path, actor="cli", type="spec.activated", payload={"spec_path": "a.md"})
        agent.emit_event_to(self.path, actor="cli", type="spec.activated", payload={"spec_path": "b.md"})
        events = list(agent.iter_events(self.path))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["payload"]["spec_path"], "a.md")
        self.assertEqual(events[1]["payload"]["spec_path"], "b.md")

    def test_iter_events_skips_corrupted_lines(self):
        # Write one good, one corrupted, one good
        agent.emit_event_to(self.path, actor="cli", type="spec.activated", payload={"spec_path": "a.md"})
        with open(self.path, "a") as f:
            f.write("this is not json\n")
        agent.emit_event_to(self.path, actor="cli", type="spec.activated", payload={"spec_path": "c.md"})
        events = list(agent.iter_events(self.path))
        self.assertEqual(len(events), 2)  # corrupted line skipped


if __name__ == "__main__":
    unittest.main()
