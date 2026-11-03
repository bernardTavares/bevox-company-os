"""Testes materializer v2 (wave-6): topological sort + label_to_real + blocked_by."""
import importlib
import json
import unittest
from unittest.mock import patch


def _reload_mat():
    from lib import materializer
    importlib.reload(materializer)
    return materializer


PROPOSAL_FIXTURE = {
    "schema_version": 2,
    "proposal_id": "test-proposal-v6",
    "dependency_mode": "hybrid",
    "target_sprint": "current",
    "computed_deps": {
        "Task 1.1": [],
        "Task 2.1": ["Task 1.1"],
        "Task 2.2": ["Task 1.1", "Task 2.1"],
    },
    "tasks": [
        {
            "provisional_id": "prov-1", "label": "Task 1.1",
            "title": "A", "project": "openclaw", "epic_id": "E10",
            "wave_ref": "E10/OH/Phase-1",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC1"],
                "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                "blocked_by_labels": [],
            },
            "description": "",
        },
        {
            "provisional_id": "prov-2", "label": "Task 2.1",
            "title": "B", "project": "openclaw", "epic_id": "E10",
            "wave_ref": "E10/OH/Phase-2",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC2"],
                "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                "blocked_by_labels": ["Task 1.1"],
            },
            "description": "",
        },
        {
            "provisional_id": "prov-3", "label": "Task 2.2",
            "title": "C", "project": "openclaw", "epic_id": "E10",
            "wave_ref": "E10/OH/Phase-2",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC3"],
                "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                "blocked_by_labels": ["Task 1.1", "Task 2.1"],
            },
            "description": "",
        },
    ],
}


class TestMaterializerV2(unittest.TestCase):
    def test_topological_order_and_blocked_by_resolution(self):
        materializer = _reload_mat()
        calls: list = []

        def fake_run_kanban(args, actor=None):
            calls.append(tuple(args))
            if args[0] == "task" and args[1] == "add":
                idx = len([c for c in calls if c[0] == "task" and c[1] == "add"])
                return {"ok": True, "task": {"id": f"T-000{idx}"}}
            elif args[0] == "task" and args[1] == "set-dispatch-payload":
                return {"ok": True}
            return {}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            result = materializer.materialize_proposal(
                PROPOSAL_FIXTURE, target_sprint="current",
                make_ready=False, actor="test",
            )

        # Verify ordering: A before B before C (topological)
        add_calls = [c for c in calls if c[0] == "task" and c[1] == "add"]
        self.assertEqual(len(add_calls), 3)
        titles_ordered = [c[2] for c in add_calls]
        self.assertEqual(titles_ordered, ["A", "B", "C"])

        # Verify set-dispatch-payload calls: blocked_by resolved
        sdp_calls = [c for c in calls if c[0] == "task"
                     and c[1] == "set-dispatch-payload"]
        self.assertEqual(len(sdp_calls), 3)
        for c in sdp_calls:
            tid = c[2]  # task_id positional after "task set-dispatch-payload"
            p_idx = list(c).index("--payload")
            payload = json.loads(c[p_idx + 1])
            if tid == "T-0002":
                self.assertEqual(payload.get("blocked_by"), ["T-0001"])
            elif tid == "T-0003":
                self.assertEqual(sorted(payload.get("blocked_by", [])),
                                 ["T-0001", "T-0002"])
            elif tid == "T-0001":
                # Task 1.1 has no preds -> blocked_by empty list
                self.assertEqual(payload.get("blocked_by", []), [])


if __name__ == "__main__":
    unittest.main()
