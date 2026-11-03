"""Unit tests for persona / code_repo / mission_control provisioners."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.provisioners.persona import provision_persona
from lib.provisioners.code_repo import provision_code_repo
from lib.provisioners.mission_control import provision_mission_control


class TestProvisionPersona(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.openclaw = Path(self._tmp.name)
        ws = self.openclaw / "workspace-alpha"
        ws.mkdir()
        (ws / "IDENTITY.md").write_text(
            "---\npersona_status: pending\n---\n# Alpha\n"
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_prd_returns_absent(self):
        res = provision_persona("alpha", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "absent")
        self.assertEqual(res.persona_status, "no_prd")

    def test_no_workspace_returns_absent(self):
        res = provision_persona("nope", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "absent")
        self.assertIn("workspace-nope", res.error or "")

    def test_with_prd_runs_step_4(self):
        with patch(
            "lib.project_factory.step_4_persona_llm",
            return_value={"persona_status": "generated"},
        ):
            res = provision_persona(
                "alpha", openclaw_dir=self.openclaw,
                prd_text="# PRD body",
            )
        self.assertEqual(res.state, "provisioned")
        self.assertEqual(res.persona_status, "generated")

    def test_pending_returns_partial(self):
        with patch(
            "lib.project_factory.step_4_persona_llm",
            return_value={"persona_status": "pending", "error": "no LLM"},
        ):
            res = provision_persona(
                "alpha", openclaw_dir=self.openclaw,
                prd_text="# PRD body",
            )
        self.assertEqual(res.state, "partial")


class TestProvisionCodeRepo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.code_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_local_present_returns_provisioned(self):
        (self.code_dir / "alpha").mkdir()
        res = provision_code_repo("alpha", code_dir=self.code_dir)
        self.assertEqual(res.state, "provisioned")
        self.assertIn("github.com", res.github)

    def test_absent_when_no_dir(self):
        res = provision_code_repo("nope", code_dir=self.code_dir)
        self.assertEqual(res.state, "absent")
        self.assertIn("does not auto-create", res.error or "")


class TestProvisionMissionControl(unittest.TestCase):
    def test_no_op_returns_absent_without_error(self):
        """No-op stub: state=absent, error=None, note explains why."""
        res = provision_mission_control("alpha")
        self.assertEqual(res.state, "absent")
        self.assertIsNone(res.error)
        self.assertIn("implicit", res.note)


if __name__ == "__main__":
    unittest.main()
