"""Testes gate_check (wave-6): espelha wave-4 payload_gate localmente."""
import unittest

from lib import gate_check


class TestCheckTaskPayload(unittest.TestCase):
    def test_happy_with_spec_ref_string_and_ac(self):
        t = {"label": "Task 1.1", "dispatch_payload": {
            "spec_ref": "x.md",
            "acceptance_criteria": ["AC1"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_happy_with_spec_refs_plural_list(self):
        t = {"label": "T", "dispatch_payload": {
            "spec_refs": ["a.md", "b.md"],
            "acceptance_criteria": ["AC"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertTrue(ok)

    def test_missing_ac_fails(self):
        t = {"label": "T", "dispatch_payload": {"spec_ref": "x.md"}}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("acceptance_criteria", missing)

    def test_empty_ac_list_fails(self):
        t = {"label": "T", "dispatch_payload": {
            "spec_ref": "x.md", "acceptance_criteria": [],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("acceptance_criteria", missing)

    def test_missing_spec_ref_fails(self):
        t = {"label": "T", "dispatch_payload": {
            "acceptance_criteria": ["AC"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("spec_ref", missing)

    def test_empty_spec_refs_list_fails(self):
        t = {"label": "T", "dispatch_payload": {
            "spec_refs": [], "acceptance_criteria": ["AC"],
        }}
        ok, missing = gate_check.check_task_payload(t)
        self.assertFalse(ok)
        self.assertIn("spec_ref", missing)


class TestCheckProposal(unittest.TestCase):
    def test_all_tasks_valid_no_raise(self):
        proposal = {"tasks": [
            {"label": "Task 1.1", "dispatch_payload": {
                "spec_ref": "x.md", "acceptance_criteria": ["AC"]}},
            {"label": "Task 1.2", "dispatch_payload": {
                "spec_refs": ["x.md"], "acceptance_criteria": ["AC"]}},
        ]}
        gate_check.check_proposal(proposal)

    def test_one_task_missing_ac_raises(self):
        proposal = {"tasks": [
            {"label": "Task 1.1", "dispatch_payload": {
                "spec_ref": "x.md", "acceptance_criteria": ["AC"]}},
            {"label": "Task 1.2", "dispatch_payload": {"spec_ref": "x.md"}},
        ]}
        with self.assertRaises(gate_check.GateCheckFailedError) as ctx:
            gate_check.check_proposal(proposal)
        self.assertTrue(any("Task 1.2" in f for f in ctx.exception.failures))
        self.assertTrue(any("acceptance_criteria" in f for f in ctx.exception.failures))


if __name__ == "__main__":
    unittest.main()
