"""Testes payload_gate — validator puro + exceção + enforce."""
import unittest

from lib import payload_gate


class TestValidatePayload(unittest.TestCase):
    def test_empty_dict_missing_both(self):
        valid, missing = payload_gate.validate_payload({})
        self.assertFalse(valid)
        self.assertIn("spec_ref", missing)
        self.assertIn("acceptance_criteria", missing)

    def test_only_spec_ref_missing_ac(self):
        valid, missing = payload_gate.validate_payload({"spec_ref": "35_specs/x.md"})
        self.assertFalse(valid)
        self.assertEqual(missing, ["acceptance_criteria"])

    def test_only_ac_missing_spec_ref(self):
        valid, missing = payload_gate.validate_payload({"acceptance_criteria": ["AC1"]})
        self.assertFalse(valid)
        self.assertEqual(missing, ["spec_ref"])

    def test_empty_spec_ref_string_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "", "acceptance_criteria": ["AC1"],
        })
        self.assertFalse(valid)
        self.assertIn("spec_ref", missing)

    def test_empty_spec_ref_list_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": [], "acceptance_criteria": ["AC1"],
        })
        self.assertFalse(valid)
        self.assertIn("spec_ref", missing)

    def test_empty_ac_list_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "35_specs/x.md", "acceptance_criteria": [],
        })
        self.assertFalse(valid)
        self.assertEqual(missing, ["acceptance_criteria"])

    def test_ac_not_list_counts_missing(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "35_specs/x.md", "acceptance_criteria": "AC1 string",
        })
        self.assertFalse(valid)
        self.assertEqual(missing, ["acceptance_criteria"])

    def test_happy_path_string_spec_ref(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "35_specs/x.md",
            "acceptance_criteria": ["AC1: tests pass"],
        })
        self.assertTrue(valid)
        self.assertEqual(missing, [])

    def test_happy_path_list_spec_ref(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": ["35_specs/a.md", "35_specs/b.md"],
            "acceptance_criteria": ["AC1", "AC2"],
        })
        self.assertTrue(valid)
        self.assertEqual(missing, [])

    def test_extra_fields_allowed(self):
        valid, missing = payload_gate.validate_payload({
            "spec_ref": "x.md", "acceptance_criteria": ["AC"],
            "extra_field": "foo", "description": "bar",
        })
        self.assertTrue(valid)


class TestEnforcePayloadGate(unittest.TestCase):
    def test_enforce_valid_no_raise(self):
        payload_gate.enforce_payload_gate({
            "spec_ref": "x.md", "acceptance_criteria": ["AC1"],
        })

    def test_enforce_invalid_raises_with_missing(self):
        with self.assertRaises(payload_gate.PayloadIncompleteError) as ctx:
            payload_gate.enforce_payload_gate({})
        self.assertIn("spec_ref", ctx.exception.missing)
        self.assertIn("acceptance_criteria", ctx.exception.missing)
        self.assertEqual(ctx.exception.code, "PAYLOAD_INCOMPLETE")

    def test_enforce_partial_raises(self):
        with self.assertRaises(payload_gate.PayloadIncompleteError) as ctx:
            payload_gate.enforce_payload_gate({"spec_ref": "x.md"})
        self.assertEqual(ctx.exception.missing, ["acceptance_criteria"])


if __name__ == "__main__":
    unittest.main()
