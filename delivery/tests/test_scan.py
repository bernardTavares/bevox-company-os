"""Tests for scan_active_specs (gap detection + dedupe)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent


SAMPLE_SPEC = """\
# Test Spec

## Tarefas

- First task
- Second task
"""


class TestScanActiveSpecs(unittest.TestCase):
    def setUp(self):
        # Create a temporary spec file
        self.tmpdir = Path(tempfile.mkdtemp())
        self.spec_file = self.tmpdir / "test-spec.md"
        self.spec_file.write_text(SAMPLE_SPEC)

    def tearDown(self):
        self.spec_file.unlink()
        self.tmpdir.rmdir()

    def _make_state_with_active(self, spec_path: str) -> dict:
        return {
            "schema_version": 1,
            "generated_at": "2026-04-13T00:00:00.000Z",
            "from_event_id": None,
            "active_specs": {spec_path: {"activated_at": "2026-04-13T00:00:00.000Z", "activated_by_event": "evt_x"}},
            "proposals": {},
            "last_scan": None,
        }

    def test_empty_state_emits_no_proposals(self):
        state = {
            "schema_version": 1,
            "active_specs": {},
            "proposals": {},
            "last_scan": None,
        }
        new_proposals = agent.scan_active_specs(state)
        self.assertEqual(new_proposals, [])

    def test_active_spec_emits_two_proposals(self):
        state = self._make_state_with_active(str(self.spec_file))
        new_proposals = agent.scan_active_specs(state)
        self.assertEqual(len(new_proposals), 2)
        item_texts = [p["item_text"] for p in new_proposals]
        self.assertIn("First task", item_texts)
        self.assertIn("Second task", item_texts)

    def test_dedupe_against_existing_pending(self):
        state = self._make_state_with_active(str(self.spec_file))
        # Pre-seed with one proposal matching the first task
        existing_key = agent.compute_key(str(self.spec_file), "Tarefas", "First task")
        state["proposals"]["prop_existing"] = {
            "key": existing_key,
            "spec_path": str(self.spec_file),
            "section_id": "Tarefas",
            "item_text": "First task",
            "state": "pending",
            "proposed_at": "2026-04-13T00:00:00.000Z",
            "resolved_at": None,
            "resolved_reason": None,
            "task_id": None,
        }
        new_proposals = agent.scan_active_specs(state)
        # Only "Second task" should be new
        self.assertEqual(len(new_proposals), 1)
        self.assertEqual(new_proposals[0]["item_text"], "Second task")

    def test_dedupe_against_accepted(self):
        state = self._make_state_with_active(str(self.spec_file))
        accepted_key = agent.compute_key(str(self.spec_file), "Tarefas", "First task")
        state["proposals"]["prop_accepted"] = {
            "key": accepted_key,
            "spec_path": str(self.spec_file),
            "section_id": "Tarefas",
            "item_text": "First task",
            "state": "accepted",
            "proposed_at": "...",
            "resolved_at": "...",
            "resolved_reason": None,
            "task_id": "task_1",
        }
        new_proposals = agent.scan_active_specs(state)
        self.assertEqual(len(new_proposals), 1)
        self.assertEqual(new_proposals[0]["item_text"], "Second task")

    def test_dedupe_against_rejected(self):
        state = self._make_state_with_active(str(self.spec_file))
        rejected_key = agent.compute_key(str(self.spec_file), "Tarefas", "First task")
        state["proposals"]["prop_rej"] = {
            "key": rejected_key,
            "spec_path": str(self.spec_file),
            "section_id": "Tarefas",
            "item_text": "First task",
            "state": "rejected",
            "proposed_at": "...",
            "resolved_at": "...",
            "resolved_reason": "no",
            "task_id": None,
        }
        new_proposals = agent.scan_active_specs(state)
        self.assertEqual(len(new_proposals), 1)

    def test_inactive_spec_skipped(self):
        state = {
            "schema_version": 1,
            "active_specs": {},  # no active
            "proposals": {},
            "last_scan": None,
        }
        new_proposals = agent.scan_active_specs(state)
        self.assertEqual(new_proposals, [])


if __name__ == "__main__":
    unittest.main()
