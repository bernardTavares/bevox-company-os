"""Tests for state.json projection from events.jsonl."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent


def _events_to_path(events: list[dict]) -> Path:
    """Helper: write a list of pre-built events to a temp jsonl, return path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for evt in events:
        tmp.write(json.dumps(evt) + "\n")
    tmp.close()
    return Path(tmp.name)


class TestProjectionEmpty(unittest.TestCase):
    def test_empty_events_gives_empty_state(self):
        path = _events_to_path([])
        try:
            state = agent.project_state(path)
            self.assertEqual(state["active_specs"], {})
            self.assertEqual(state["proposals"], {})
            self.assertEqual(state["schema_version"], 1)
        finally:
            path.unlink()


class TestProjectionSpecLifecycle(unittest.TestCase):
    def test_spec_activated_appears_in_active_specs(self):
        evt = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "35_specs/foo.md"})
        path = _events_to_path([evt])
        try:
            state = agent.project_state(path)
            self.assertIn("35_specs/foo.md", state["active_specs"])
            self.assertEqual(state["active_specs"]["35_specs/foo.md"]["activated_by_event"], evt["event_id"])
        finally:
            path.unlink()

    def test_spec_archived_removes_from_active(self):
        e1 = agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"})
        e2 = agent.make_event(actor="cli", type="spec.archived", payload={"spec_path": "x.md", "reason": "delivered"})
        path = _events_to_path([e1, e2])
        try:
            state = agent.project_state(path)
            self.assertNotIn("x.md", state["active_specs"])
        finally:
            path.unlink()


class TestProjectionProposalLifecycle(unittest.TestCase):
    def _make_proposal_evt(self, proposal_id="prop_1", key="key123abc"):
        return agent.make_event(
            actor="delivery-agent",
            type="task.proposed",
            payload={
                "proposal_id": proposal_id,
                "key": key,
                "spec_path": "x.md",
                "section_id": "Tarefas",
                "item_text": "do thing",
                "run_id": "run_1",
            },
        )

    def test_task_proposed_creates_pending(self):
        evt = self._make_proposal_evt()
        path = _events_to_path([evt])
        try:
            state = agent.project_state(path)
            self.assertIn("prop_1", state["proposals"])
            self.assertEqual(state["proposals"]["prop_1"]["state"], "pending")
            self.assertEqual(state["proposals"]["prop_1"]["key"], "key123abc")
        finally:
            path.unlink()

    def test_task_created_marks_accepted(self):
        e1 = self._make_proposal_evt()
        e2 = agent.make_event(
            actor="cli",
            type="task.created",
            payload={"proposal_id": "prop_1", "key": "key123abc", "task_id": "task_1"},
        )
        path = _events_to_path([e1, e2])
        try:
            state = agent.project_state(path)
            self.assertEqual(state["proposals"]["prop_1"]["state"], "accepted")
            self.assertEqual(state["proposals"]["prop_1"]["task_id"], "task_1")
        finally:
            path.unlink()

    def test_task_rejected_marks_rejected_with_reason(self):
        e1 = self._make_proposal_evt()
        e2 = agent.make_event(
            actor="cli",
            type="task.rejected",
            payload={"proposal_id": "prop_1", "key": "key123abc", "reason": "duplicate"},
        )
        path = _events_to_path([e1, e2])
        try:
            state = agent.project_state(path)
            self.assertEqual(state["proposals"]["prop_1"]["state"], "rejected")
            self.assertEqual(state["proposals"]["prop_1"]["resolved_reason"], "duplicate")
        finally:
            path.unlink()

    def test_proposal_expired_marks_expired(self):
        e1 = self._make_proposal_evt()
        e2 = agent.make_event(
            actor="cli",
            type="proposal.expired",
            payload={"proposal_id": "prop_1", "key": "key123abc", "reason": "spec_archived", "triggered_by": "evt_xyz"},
        )
        path = _events_to_path([e1, e2])
        try:
            state = agent.project_state(path)
            self.assertEqual(state["proposals"]["prop_1"]["state"], "expired")
        finally:
            path.unlink()


class TestRebuildState(unittest.TestCase):
    def test_rebuild_state_writes_state_json(self):
        events_path = _events_to_path([
            agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"}),
        ])
        state_path = Path(tempfile.mkstemp(suffix=".json")[1])
        try:
            agent.rebuild_state(events_path, state_path)
            data = json.loads(state_path.read_text())
            self.assertIn("x.md", data["active_specs"])
        finally:
            events_path.unlink()
            state_path.unlink()

    def test_rebuild_state_is_idempotent(self):
        events_path = _events_to_path([
            agent.make_event(actor="cli", type="spec.activated", payload={"spec_path": "x.md"}),
        ])
        state_path = Path(tempfile.mkstemp(suffix=".json")[1])
        try:
            agent.rebuild_state(events_path, state_path)
            first = state_path.read_text()
            agent.rebuild_state(events_path, state_path)
            second = state_path.read_text()
            # generated_at differs but the rest should be stable; compare by parsed JSON minus generated_at
            d1 = json.loads(first)
            d2 = json.loads(second)
            d1.pop("generated_at", None)
            d2.pop("generated_at", None)
            self.assertEqual(d1, d2)
        finally:
            events_path.unlink()
            state_path.unlink()


if __name__ == "__main__":
    unittest.main()
