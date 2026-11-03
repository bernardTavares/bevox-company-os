"""Wave-8 fixes for materializer: Bug #3a (allowed_keys) + #3b (set-blocked-by CLI call)."""
import importlib
import unittest
from unittest.mock import patch


def _reload_mat():
    from lib import materializer
    importlib.reload(materializer)
    return materializer


WAVE8_PROPOSAL_FIXTURE = {
    "schema_version": 2,
    "proposal_id": "wave-8-test-proposal",
    "dependency_mode": "hybrid",
    "target_sprint": "current",
    "computed_deps": {
        "Task 1.1": [],
        "Task 2.1": ["Task 1.1"],
    },
    "tasks": [
        {
            "provisional_id": "prov-1", "label": "Task 1.1",
            "title": "A", "project": "test-project", "epic_id": "E10",
            "wave_ref": "E10/OH/wave-8-fixture/Phase-1",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC1"],
                "goal": "create A", "plan_ref": "p.md", "plan_anchor": "a",
                "blocked_by_labels": [],
            },
            "description": "",
        },
        {
            "provisional_id": "prov-2", "label": "Task 2.1",
            "title": "B", "project": "test-project", "epic_id": "E10",
            "wave_ref": "E10/OH/wave-8-fixture/Phase-2",
            "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC2"],
                "goal": "create B", "plan_ref": "p.md", "plan_anchor": "a",
                "blocked_by_labels": ["Task 1.1"],
            },
            "description": "",
        },
    ],
}


class TestWave8AllowedKeys(unittest.TestCase):
    """Bug #3a: _DISPATCH_PAYLOAD_ALLOWED inclui blocked_by_labels."""

    def test_blocked_by_labels_in_allowed_set(self):
        materializer = _reload_mat()
        self.assertIn("blocked_by_labels", materializer._DISPATCH_PAYLOAD_ALLOWED)

    def test_materialize_accepts_blocked_by_labels(self):
        """Sanity: proposal com blocked_by_labels nao raise INVALID_PAYLOAD."""
        materializer = _reload_mat()
        calls = []

        def fake_run_kanban(args, actor=None):
            calls.append(tuple(args))
            if args[0] == "task" and args[1] == "add":
                idx = sum(1 for c in calls if c[:2] == ("task", "add"))
                return {"ok": True, "task": {"id": f"T-99{idx:02d}"}}
            return {"ok": True}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            result = materializer.materialize_proposal(
                WAVE8_PROPOSAL_FIXTURE, target_sprint="current",
                make_ready=False, actor="test-wave8",
            )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["task_id"], "T-9901")
        self.assertEqual(result[1]["task_id"], "T-9902")
        self.assertEqual(result[1]["preds"], ["T-9901"])


class TestWave8SetBlockedByCall(unittest.TestCase):
    """Bug #3b: materializer chama `task set-blocked-by` quando preds nao-vazio."""

    def test_set_blocked_by_called_for_task_with_preds(self):
        materializer = _reload_mat()
        calls = []

        def fake_run_kanban(args, actor=None):
            calls.append(tuple(args))
            if args[0] == "task" and args[1] == "add":
                idx = sum(1 for c in calls if c[:2] == ("task", "add"))
                return {"ok": True, "task": {"id": f"T-55{idx:02d}"}}
            return {"ok": True}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            materializer.materialize_proposal(
                WAVE8_PROPOSAL_FIXTURE, target_sprint="current",
                make_ready=False, actor="test-wave8",
            )

        set_blocked_by_calls = [
            c for c in calls
            if len(c) >= 2 and c[0] == "task" and c[1] == "set-blocked-by"
        ]
        # Task 1.1 (preds vazios) -> 0 calls; Task 2.1 (preds=['Task 1.1']) -> 1 call
        self.assertEqual(len(set_blocked_by_calls), 1,
                         f"esperava 1 call set-blocked-by, calls={calls}")
        call = set_blocked_by_calls[0]
        self.assertEqual(call[2], "T-5502",
                         f"set-blocked-by deve ser no Task 2.1 (T-5502), call={call}")
        # Format esperado: ("task", "set-blocked-by", task_id, "--preds", *preds)
        preds_start = list(call).index("--preds") + 1
        self.assertEqual(call[preds_start:], ("T-5501",),
                         f"--preds deve apontar pra T-5501, call={call}")

    def test_set_blocked_by_NOT_called_when_preds_empty(self):
        """Task 1.1 (sem preds) nao deve disparar set-blocked-by call."""
        materializer = _reload_mat()
        proposal_single = {
            "schema_version": 2,
            "proposal_id": "single",
            "dependency_mode": "hybrid",
            "target_sprint": "current",
            "computed_deps": {"Task 1.1": []},
            "tasks": [
                {
                    "provisional_id": "prov-1", "label": "Task 1.1",
                    "title": "Solo", "project": "test-project", "epic_id": "E10",
                    "wave_ref": "E10/OH/solo/Phase-1",
                    "dispatch_payload": {
                        "spec_refs": ["x.md"], "acceptance_criteria": ["AC"],
                        "goal": "g", "plan_ref": "p", "plan_anchor": "a",
                        "blocked_by_labels": [],
                    },
                    "description": "",
                },
            ],
        }
        calls = []

        def fake_run_kanban(args, actor=None):
            calls.append(tuple(args))
            if args[0] == "task" and args[1] == "add":
                return {"ok": True, "task": {"id": "T-7701"}}
            return {"ok": True}

        with patch.object(materializer, "_run_kanban", side_effect=fake_run_kanban):
            materializer.materialize_proposal(
                proposal_single, target_sprint="current",
                make_ready=False, actor="test-wave8",
            )

        set_blocked_by_calls = [
            c for c in calls
            if len(c) >= 2 and c[0] == "task" and c[1] == "set-blocked-by"
        ]
        self.assertEqual(len(set_blocked_by_calls), 0,
                         f"0 calls set-blocked-by pra task sem preds, calls={calls}")


if __name__ == "__main__":
    unittest.main()
