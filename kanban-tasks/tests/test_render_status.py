"""Tests for pure rendering helpers in lib.render_status (W3).

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w3-v1.md
"""
import json
import re
import unittest

from lib.render_status import (
    CAPABILITY_ORDER,
    build_json_payload,
    compute_diff,
    render_dispatcher_table,
    render_single_project,
)


# A minimal "all-provisioned" detected fixture.
def _all_provisioned_detected() -> dict:
    return {cap: {"state": "provisioned"} for cap in CAPABILITY_ORDER}


def _all_provisioned_declared() -> dict:
    return {cap: {"state": "provisioned"} for cap in CAPABILITY_ORDER}


class TestComputeDiff(unittest.TestCase):
    def test_no_drift_when_states_match(self):
        d = compute_diff(_all_provisioned_declared(), _all_provisioned_detected())
        for cap in CAPABILITY_ORDER:
            self.assertFalse(d[cap]["drift"], f"unexpected drift on {cap}")

    def test_drift_flag_set_when_declared_provisioned_detected_partial(self):
        declared = _all_provisioned_declared()
        detected = _all_provisioned_detected()
        detected["knowledge_slot"] = {
            "state": "partial", "folders_present": 5, "folders_total": 9,
        }
        d = compute_diff(declared, detected)
        self.assertTrue(d["knowledge_slot"]["drift"])
        self.assertIn("declared=provisioned", d["knowledge_slot"]["drift_reason"])
        self.assertIn("detected=partial", d["knowledge_slot"]["drift_reason"])
        # Other capabilities still no drift.
        self.assertFalse(d["code_repo"]["drift"])

    def test_skipped_does_not_drift(self):
        declared = _all_provisioned_declared()
        detected = _all_provisioned_detected()
        detected["knowledge_slot"] = {
            "state": "skipped", "drift_reason": "skipped via flag",
        }
        d = compute_diff(declared, detected)
        self.assertFalse(d["knowledge_slot"]["drift"])
        # But drift_reason still surfaced as caveat.
        self.assertEqual(d["knowledge_slot"]["drift_reason"], "skipped via flag")

    def test_no_detect_means_no_drift(self):
        declared = _all_provisioned_declared()
        d = compute_diff(declared, None)
        for cap in CAPABILITY_ORDER:
            self.assertFalse(d[cap]["drift"])
            self.assertIsNone(d[cap]["detected"])

    def test_uses_detected_drift_reason_when_present(self):
        declared = {"knowledge_slot": {"state": "provisioned"}}
        detected = {"knowledge_slot": {
            "state": "partial",
            "drift_reason": "5/9 folders ADR-010 presentes",
        }}
        # fill rest with absent so loop covers them.
        for cap in CAPABILITY_ORDER:
            declared.setdefault(cap, {"state": "absent"})
            detected.setdefault(cap, {"state": "absent"})
        d = compute_diff(declared, detected)
        self.assertTrue(d["knowledge_slot"]["drift"])
        self.assertEqual(
            d["knowledge_slot"]["drift_reason"], "5/9 folders ADR-010 presentes",
        )


class TestRenderSingleProject(unittest.TestCase):
    def test_renders_8_capability_rows(self):
        meta = {"source": "user_created", "created_at": "2026-04-15"}
        diff = compute_diff(
            _all_provisioned_declared(), _all_provisioned_detected(),
        )
        output = render_single_project("foo", meta, diff)
        for cap in CAPABILITY_ORDER:
            self.assertIn(cap, output, f"capability {cap} missing in render")
        self.assertIn("foo", output)
        self.assertIn("Summary:", output)
        self.assertIn("8 provisioned", output)
        self.assertIn("0 drift detected", output)

    def test_drift_marker_in_drift_column(self):
        declared = _all_provisioned_declared()
        detected = _all_provisioned_detected()
        detected["knowledge_slot"] = {
            "state": "partial",
            "folders_present": 5,
            "folders_total": 9,
            "drift_reason": "5/9 folders ADR-010",
        }
        diff = compute_diff(declared, detected)
        meta = {"source": "adopted", "created_at": "2026-04-15"}
        output = render_single_project("bar", meta, diff)
        self.assertIn("DRIFT", output)
        self.assertIn("1 drift detected", output)

    def test_no_ansi_escapes(self):
        meta = {"source": "x", "created_at": "y"}
        diff = compute_diff(
            _all_provisioned_declared(), _all_provisioned_detected(),
        )
        output = render_single_project("foo", meta, diff)
        self.assertNotIn("\033[", output)
        self.assertNotIn("\x1b", output)

    def test_detect_skipped_label(self):
        meta = {"source": "x", "created_at": "y"}
        diff = compute_diff(_all_provisioned_declared(), None)
        output = render_single_project("foo", meta, diff, detect_skipped=True)
        self.assertIn("(skipped)", output)


class TestRenderDispatcherTable(unittest.TestCase):
    def test_renders_all_slugs_alphabetical(self):
        diffs = {}
        for slug in ["zeta", "alpha", "mu"]:
            diffs[slug] = compute_diff(
                _all_provisioned_declared(), _all_provisioned_detected(),
            )
        output = render_dispatcher_table(diffs)
        idx_alpha = output.find("alpha")
        idx_mu = output.find("mu")
        idx_zeta = output.find("zeta")
        self.assertLess(idx_alpha, idx_mu)
        self.assertLess(idx_mu, idx_zeta)

    def test_single_letter_codes(self):
        declared = _all_provisioned_declared()
        detected = _all_provisioned_detected()
        # Mix states.
        detected["knowledge_slot"] = {"state": "partial"}
        detected["mission_control"] = {"state": "absent"}
        declared["mission_control"] = {"state": "absent"}
        # Force drift on knowledge_slot for the '?' code.
        diff = compute_diff(declared, detected)
        out = render_dispatcher_table({"x": diff})
        # Header row has short codes.
        self.assertIn("code", out)
        self.assertIn("know", out)
        # Data row has P, ?, -.
        # Strip header lines, look at data line.
        data_line = [
            ln for ln in out.splitlines() if ln.startswith("x ")
        ][0]
        self.assertIn(" P ", data_line)  # provisioned
        self.assertIn(" ? ", data_line)  # drift code
        self.assertIn(" - ", data_line)  # absent

    def test_empty_dispatcher(self):
        output = render_dispatcher_table({})
        self.assertIn("no projects", output)

    def test_drift_count_column(self):
        declared = _all_provisioned_declared()
        detected = _all_provisioned_detected()
        detected["knowledge_slot"] = {"state": "partial"}
        diff = compute_diff(declared, detected)
        out = render_dispatcher_table({"x": diff})
        # Drift column on data row should show 1.
        data_line = [ln for ln in out.splitlines() if ln.startswith("x ")][0]
        self.assertTrue(
            data_line.rstrip().endswith("1"),
            f"expected drift count 1 at end of row, got: {data_line!r}",
        )

    def test_no_ansi_escapes(self):
        diff = compute_diff(
            _all_provisioned_declared(), _all_provisioned_detected(),
        )
        out = render_dispatcher_table({"x": diff})
        self.assertFalse(re.search(r"\x1b\[", out))


class TestBuildJsonPayload(unittest.TestCase):
    def test_shape_matches_adr013_contract(self):
        meta = {"source": "adopted", "created_at": "2026-04-15"}
        diff = compute_diff(
            _all_provisioned_declared(), _all_provisioned_detected(),
        )
        payload = build_json_payload(
            "2026-05-07T00:00:00Z", {"foo": (meta, diff)},
        )
        # Round-trip through json so we test it's serializable.
        s = json.dumps(payload)
        parsed = json.loads(s)
        self.assertEqual(parsed["schema_version"], 1)
        self.assertEqual(parsed["generated_at"], "2026-05-07T00:00:00Z")
        self.assertIn("foo", parsed["projects"])
        proj = parsed["projects"]["foo"]
        self.assertEqual(proj["source"], "adopted")
        self.assertEqual(proj["created_at"], "2026-04-15")
        self.assertEqual(proj["drifts"], [])
        for cap in CAPABILITY_ORDER:
            self.assertIn(cap, proj["capabilities"])
            self.assertIn("declared", proj["capabilities"][cap])
            self.assertIn("detected", proj["capabilities"][cap])
            self.assertIn("drift", proj["capabilities"][cap])

    def test_drift_listed_in_drifts_array(self):
        declared = _all_provisioned_declared()
        detected = _all_provisioned_detected()
        detected["knowledge_slot"] = {
            "state": "partial", "drift_reason": "5/9 folders",
        }
        diff = compute_diff(declared, detected)
        meta = {"source": "x", "created_at": "y"}
        payload = build_json_payload("t", {"foo": (meta, diff)})
        proj = payload["projects"]["foo"]
        self.assertEqual(proj["drifts"], ["knowledge_slot"])
        self.assertEqual(
            proj["capabilities"]["knowledge_slot"]["drift_reason"], "5/9 folders",
        )

    def test_no_detect_nullifies_detected(self):
        declared = _all_provisioned_declared()
        diff = compute_diff(declared, None)
        meta = {"source": "x", "created_at": "y"}
        payload = build_json_payload(
            "t", {"foo": (meta, diff)}, detect_skipped=True,
        )
        proj = payload["projects"]["foo"]
        self.assertTrue(payload["detect_skipped"])
        for cap in CAPABILITY_ORDER:
            self.assertIsNone(proj["capabilities"][cap]["detected"])
            self.assertFalse(proj["capabilities"][cap]["drift"])


if __name__ == "__main__":
    unittest.main()
