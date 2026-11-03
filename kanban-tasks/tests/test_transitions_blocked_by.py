"""Testes puros transitions.py wave-5: validate_blocked_by_field, detect_cycle, can_move_to_ready."""
import unittest

from lib import transitions


class TestValidateBlockedByField(unittest.TestCase):
    def test_none_is_valid(self):
        valid, errors = transitions.validate_blocked_by_field(None)
        self.assertTrue(valid)
        self.assertEqual(errors, [])

    def test_empty_list_is_valid(self):
        valid, errors = transitions.validate_blocked_by_field([])
        self.assertTrue(valid)

    def test_string_list_with_T_prefix_is_valid(self):
        valid, errors = transitions.validate_blocked_by_field(["T-0001", "T-0042"])
        self.assertTrue(valid)

    def test_string_not_list_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field("T-0001")
        self.assertFalse(valid)
        self.assertIn("blocked_by_must_be_list", errors)

    def test_dict_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field({"T-0001": 1})
        self.assertFalse(valid)
        self.assertIn("blocked_by_must_be_list", errors)

    def test_non_T_prefix_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field(["T-0001", "X-0042"])
        self.assertFalse(valid)
        self.assertTrue(any("blocked_by[1]" in e for e in errors))

    def test_non_string_item_is_invalid(self):
        valid, errors = transitions.validate_blocked_by_field(["T-0001", 123])
        self.assertFalse(valid)
        self.assertTrue(any("blocked_by[1]" in e for e in errors))


class TestDetectCycle(unittest.TestCase):
    def _state(self, tasks):
        """Helper: constroi state com tasks = [{"id": ..., "blocked_by": [...]}, ...]."""
        return {"tasks": [
            {"id": t["id"], "dispatch_payload": {"blocked_by": t.get("blocked_by", [])}}
            for t in tasks
        ]}

    def test_self_cycle(self):
        state = self._state([])
        cycle = transitions.detect_cycle(state, "T-A", ["T-A"])
        self.assertEqual(cycle, ["T-A", "T-A"])

    def test_two_node_cycle(self):
        state = self._state([{"id": "T-B", "blocked_by": ["T-A"]}])
        cycle = transitions.detect_cycle(state, "T-A", ["T-B"])
        self.assertTrue(len(cycle) >= 2)
        self.assertIn("T-A", cycle)
        self.assertIn("T-B", cycle)

    def test_three_node_cycle(self):
        state = self._state([
            {"id": "T-B", "blocked_by": ["T-C"]},
            {"id": "T-C", "blocked_by": ["T-A"]},
        ])
        cycle = transitions.detect_cycle(state, "T-A", ["T-B"])
        self.assertTrue(len(cycle) >= 3)

    def test_no_cycle_linear_chain(self):
        state = self._state([
            {"id": "T-B", "blocked_by": []},
            {"id": "T-C", "blocked_by": []},
        ])
        cycle = transitions.detect_cycle(state, "T-A", ["T-B", "T-C"])
        self.assertEqual(cycle, [])

    def test_no_cycle_shared_ancestor_diamond(self):
        """T-A -> T-B, T-A -> T-C, T-B -> T-D, T-C -> T-D (diamond, no cycle)."""
        state = self._state([
            {"id": "T-A", "blocked_by": []},
            {"id": "T-B", "blocked_by": ["T-A"]},
            {"id": "T-C", "blocked_by": ["T-A"]},
        ])
        cycle = transitions.detect_cycle(state, "T-D", ["T-B", "T-C"])
        self.assertEqual(cycle, [])

    def test_nonexistent_pred_doesnt_false_positive(self):
        """Pred em blocked_by que nao existe no state: detect_cycle NAO reporta ciclo
        (pred missing eh validacao separada). Trata como folha."""
        state = self._state([])
        cycle = transitions.detect_cycle(state, "T-A", ["T-PHANTOM"])
        self.assertEqual(cycle, [])


class TestCanMoveToReady(unittest.TestCase):
    def _make_task(self, task_id, status="backlog", blocked_by=None):
        return {
            "id": task_id, "status": status,
            "dispatch_payload": {"blocked_by": blocked_by or []},
        }

    def _state(self, tasks):
        return {"tasks": tasks}

    def test_no_preds_can_move(self):
        task = self._make_task("T-A")
        state = self._state([task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_all_preds_done_can_move(self):
        preds = [
            self._make_task("T-A", status="done"),
            self._make_task("T-B", status="done"),
        ]
        task = self._make_task("T-C", blocked_by=["T-A", "T-B"])
        state = self._state(preds + [task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertTrue(ok)

    def test_one_pred_not_done_blocks(self):
        preds = [
            self._make_task("T-A", status="done"),
            self._make_task("T-B", status="backlog"),
        ]
        task = self._make_task("T-C", blocked_by=["T-A", "T-B"])
        state = self._state(preds + [task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertFalse(ok)
        self.assertTrue(any("T-B" in m for m in missing))

    def test_pred_not_found_blocks(self):
        task = self._make_task("T-C", blocked_by=["T-PHANTOM"])
        state = self._state([task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertFalse(ok)
        self.assertTrue(any("not_found" in m for m in missing))

    def test_pred_rejected_blocks(self):
        preds = [self._make_task("T-A", status="rejected")]
        task = self._make_task("T-C", blocked_by=["T-A"])
        state = self._state(preds + [task])
        ok, missing = transitions.can_move_to_ready(task, state)
        self.assertFalse(ok)
        self.assertTrue(any("rejected" in m for m in missing))


if __name__ == "__main__":
    unittest.main()
