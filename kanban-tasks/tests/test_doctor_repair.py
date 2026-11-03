"""Tests for lib.doctor.repair — drift → provisioner mapping.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w5-v1.md
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.capability_detect import DetectPaths
from lib.doctor.repair import _is_auto_repairable, repair_drift
from lib.doctor.scanner import DriftRow


def _drift(**overrides) -> DriftRow:
    base = dict(
        slug="alpha",
        capability="workspace",
        declared_state="provisioned",
        detected_state="partial",
        drift_reason=None,
        declared={"state": "provisioned"},
        detected={"state": "partial"},
    )
    base.update(overrides)
    return DriftRow(**base)


class TestIsAutoRepairable(unittest.TestCase):

    def test_partial_auto_repairable(self):
        d = _drift(declared_state="provisioned", detected_state="partial")
        self.assertTrue(_is_auto_repairable(d))

    def test_absent_when_declared_provisioned_auto_repairable(self):
        d = _drift(declared_state="provisioned", detected_state="absent")
        self.assertTrue(_is_auto_repairable(d))

    def test_inverse_drift_auto_repairable(self):
        d = _drift(declared_state="absent", detected_state="provisioned")
        self.assertTrue(_is_auto_repairable(d))

    def test_drifted_state_not_auto_repairable(self):
        d = _drift(declared_state="provisioned", detected_state="drifted")
        self.assertFalse(_is_auto_repairable(d))


class _RepairBase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.openclaw_dir = root / "openclaw"
        self.openclaw_dir.mkdir()
        self.meta_path = self.openclaw_dir / "projects-meta.json"
        self.meta_path.write_text(json.dumps({
            "version": 1,
            "projects": {
                "alpha": {
                    "name": "alpha",
                    "source": "user_created",
                    "capabilities_schema_version": 1,
                    "capabilities": {
                        n: {"state": "absent"} for n in (
                            "code_repo", "knowledge_slot", "kanban_sprints",
                            "workspace", "persona", "bot",
                            "telegram_topics", "mission_control",
                        )
                    },
                },
            },
        }, indent=2))
        self.paths = DetectPaths(
            kb_dir=root / "kb",
            openclaw_dir=self.openclaw_dir,
            code_dir=root / "code",
            org="bernardTavares",
        )

    def tearDown(self):
        self._tmp.cleanup()


class TestRepairAmbiguousAutoConfirm(_RepairBase):

    def test_drifted_state_skipped_in_auto_confirm(self):
        d = _drift(declared_state="provisioned", detected_state="drifted")
        outcome = repair_drift(
            d, paths=self.paths, meta_path=self.meta_path,
            opts={}, auto_confirm=True, prompt_fn=None,
        )
        self.assertEqual(outcome.action, "ambiguous")


class TestRepairUserDeclined(_RepairBase):

    def test_interactive_declined_returns_user_declined(self):
        d = _drift()
        outcome = repair_drift(
            d, paths=self.paths, meta_path=self.meta_path,
            opts={}, auto_confirm=False,
            prompt_fn=lambda msg: False,  # user says no
        )
        self.assertEqual(outcome.action, "user_declined")


class TestRepairInverseDrift(_RepairBase):

    def test_inverse_drift_auto_confirm_writes_meta(self):
        # detected says provisioned, meta says absent → flip meta to provisioned.
        d = _drift(
            declared_state="absent",
            detected_state="provisioned",
            declared={"state": "absent"},
            detected={"state": "provisioned", "path": "/some/path"},
        )
        outcome = repair_drift(
            d, paths=self.paths, meta_path=self.meta_path,
            opts={}, auto_confirm=True, prompt_fn=None,
        )
        self.assertEqual(outcome.action, "repaired")
        self.assertEqual(outcome.new_state, "provisioned")
        meta = json.loads(self.meta_path.read_text())
        cap = meta["projects"]["alpha"]["capabilities"]["workspace"]
        self.assertEqual(cap["state"], "provisioned")
        # Detected path got merged in.
        self.assertEqual(cap.get("path"), "/some/path")


class TestRepairProvisioner(_RepairBase):

    def test_partial_invokes_provisioner_via_mock(self):
        d = _drift(declared_state="provisioned", detected_state="partial")
        # Patch _run_provisioner to return a successful result.
        fake_result = {
            "state": "provisioned",
            "fields": {"path": "/ws/alpha"},
            "error": None,
        }
        with patch(
            "lib.doctor.repair._run_provisioner", return_value=fake_result
        ) as mock_prov:
            outcome = repair_drift(
                d, paths=self.paths, meta_path=self.meta_path,
                opts={}, auto_confirm=True, prompt_fn=None,
            )
        mock_prov.assert_called_once()
        self.assertEqual(outcome.action, "repaired")
        self.assertEqual(outcome.new_state, "provisioned")
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(
            meta["projects"]["alpha"]["capabilities"]["workspace"]["state"],
            "provisioned",
        )

    def test_provisioner_unsupported_returns_unsupported(self):
        d = _drift(declared_state="provisioned", detected_state="partial")
        with patch(
            "lib.doctor.repair._run_provisioner",
            return_value={"state": "unsupported", "fields": {},
                          "reason": "no impl"},
        ):
            outcome = repair_drift(
                d, paths=self.paths, meta_path=self.meta_path,
                opts={}, auto_confirm=True, prompt_fn=None,
            )
        self.assertEqual(outcome.action, "unsupported")

    def test_provisioner_raises_returns_skipped(self):
        d = _drift(declared_state="provisioned", detected_state="partial")
        with patch(
            "lib.doctor.repair._run_provisioner",
            side_effect=RuntimeError("boom"),
        ):
            outcome = repair_drift(
                d, paths=self.paths, meta_path=self.meta_path,
                opts={}, auto_confirm=True, prompt_fn=None,
            )
        self.assertEqual(outcome.action, "skipped")
        self.assertIn("boom", outcome.reason)


if __name__ == "__main__":
    unittest.main()
