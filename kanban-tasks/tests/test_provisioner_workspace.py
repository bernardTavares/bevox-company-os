"""Unit tests for lib.provisioners.workspace.provision_workspace."""
import tempfile
import unittest
from pathlib import Path

from lib.provisioners.workspace import provision_workspace, WorkspaceResult


class TestProvisionWorkspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.openclaw = Path(self._tmp.name) / "openclaw"
        self.openclaw.mkdir()
        # Minimal workspace-template required by step_3.
        wt = self.openclaw / "workspace-template"
        wt.mkdir()
        (wt / "IDENTITY.md").write_text(
            "---\npersona_status: pending\n---\n# {{SLUG}} ({{DOMAIN}})\n"
        )
        (wt / "MEMORY.md").write_text("# {{SLUG}} memory")

    def tearDown(self):
        self._tmp.cleanup()

    def test_provisions_partial_when_identity_pending(self):
        # IDENTITY.md exists but persona_status is pending → provisioner
        # creates workspace dir; detect mark of "provisioned" requires
        # actual file presence (which we have).
        res = provision_workspace(
            "alpha",
            openclaw_dir=self.openclaw,
            name="Alpha", domain="Tech",
            date_str="2026-05-07",
        )
        self.assertIsInstance(res, WorkspaceResult)
        # IDENTITY.md gets written from template → state=provisioned
        self.assertEqual(res.state, "provisioned")
        self.assertTrue((self.openclaw / "workspace-alpha" / "IDENTITY.md").is_file())
        self.assertFalse(res.already_existed)

    def test_idempotent_already_existed(self):
        res1 = provision_workspace(
            "alpha", openclaw_dir=self.openclaw, name="Alpha",
        )
        self.assertFalse(res1.already_existed)
        res2 = provision_workspace(
            "alpha", openclaw_dir=self.openclaw, name="Alpha",
        )
        self.assertTrue(res2.already_existed)

    def test_template_missing_returns_absent(self):
        # Remove template
        import shutil
        shutil.rmtree(self.openclaw / "workspace-template")
        res = provision_workspace("alpha", openclaw_dir=self.openclaw)
        self.assertEqual(res.state, "absent")
        self.assertIn("template_missing", (res.error or ""))


if __name__ == "__main__":
    unittest.main()
