"""Unit tests for lib.provisioners.knowledge.provision_knowledge.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w2-v1.md
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from lib.provisioners.knowledge import (
    CANONICAL_FOLDERS,
    ProvisionResult,
    provision_knowledge,
)
from lib.provisioners._helpers import HelperError


def _fake_skill_lib(bk: Path) -> Path:
    """Create the helper script files (empty stubs) so the path-existence
    guard in provision_knowledge passes. Tests then mock subprocess.run."""
    lib_dir = bk / "99_templates" / "skill-bevox-knowledge-contribute" / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)
    for name in ("slot_resolve.sh", "git_open_draft.sh", "git_commit_push.sh"):
        (lib_dir / name).write_text("#!/usr/bin/env bash\nexit 0\n")
    return lib_dir


class TestProvisionKnowledgeHappyPath(unittest.TestCase):
    """Mock all 3 helpers; verify ordering, folder creation, return shape."""

    def test_calls_helpers_in_order_and_creates_9_folders(self):
        with tempfile.TemporaryDirectory() as td:
            bk = Path(td) / "bevox-knowledge"
            bk.mkdir()
            _fake_skill_lib(bk)
            wt = Path(td) / "wt"
            wt.mkdir()

            calls = []

            def fake_run(cmd, **kwargs):
                # cmd[0] = "bash", cmd[1] = absolute helper path
                helper = Path(cmd[1]).name
                calls.append(helper)
                if helper == "slot_resolve.sh":
                    return MagicMock(returncode=0, stdout="ok\n", stderr="")
                if helper == "git_open_draft.sh":
                    return MagicMock(returncode=0, stdout=f"{wt}\n", stderr="")
                if helper == "git_commit_push.sh":
                    return MagicMock(
                        returncode=0,
                        stdout=(
                            "abc123def456\n"
                            "https://github.com/bernardTavares/bevox-knowledge"
                            "/tree/draft/foo-knowledge-bootstrap\n"
                        ),
                        stderr="",
                    )
                raise AssertionError(f"unexpected helper {helper}")

            with patch(
                "lib.provisioners._helpers.subprocess.run",
                side_effect=fake_run,
            ):
                result = provision_knowledge("bevox-direct", bk_path=bk)

            # Helpers called in correct order
            self.assertEqual(calls, [
                "slot_resolve.sh",
                "git_open_draft.sh",
                "git_commit_push.sh",
            ])

            # Result shape
            self.assertIsInstance(result, ProvisionResult)
            self.assertEqual(result.state, "provisioned")
            self.assertEqual(result.slot, "bevox-direct")
            self.assertEqual(result.branch, "draft/bevox-direct-knowledge-bootstrap")
            self.assertEqual(result.worktree_path, str(wt))
            self.assertEqual(result.commit_hash, "abc123def456")
            self.assertIn("draft/foo-knowledge-bootstrap", result.branch_url or "")
            self.assertFalse(result.prd_committed)

            # All 9 folders created in the worktree, each with .gitkeep
            for folder in CANONICAL_FOLDERS:
                d = wt / folder / "bevox-direct"
                self.assertTrue(d.is_dir(), f"missing {d}")
                self.assertTrue((d / ".gitkeep").exists(), f"missing gitkeep in {d}")
            self.assertEqual(len(result.folders_created), 9)


class TestProvisionKnowledgePrdStub(unittest.TestCase):
    """When prd_text is provided, PRD file is written into the worktree."""

    def test_writes_prd_when_text_provided(self):
        with tempfile.TemporaryDirectory() as td:
            bk = Path(td) / "bk"
            bk.mkdir()
            _fake_skill_lib(bk)
            wt = Path(td) / "wt"
            wt.mkdir()

            def fake_run(cmd, **kwargs):
                helper = Path(cmd[1]).name
                if helper == "slot_resolve.sh":
                    return MagicMock(returncode=0, stdout="", stderr="")
                if helper == "git_open_draft.sh":
                    return MagicMock(returncode=0, stdout=f"{wt}\n", stderr="")
                if helper == "git_commit_push.sh":
                    return MagicMock(
                        returncode=0,
                        stdout="hash1\nhttps://example/url\n",
                        stderr="",
                    )
                raise AssertionError(helper)

            with patch(
                "lib.provisioners._helpers.subprocess.run",
                side_effect=fake_run,
            ):
                result = provision_knowledge(
                    "openclaw",
                    bk_path=bk,
                    prd_text="# Test PRD\nbody body",
                    date_str="2026-05-07",
                )

            self.assertTrue(result.prd_committed)
            prd_path = wt / "10_prd" / "openclaw" / "2026-05-07-openclaw-prd.md"
            self.assertTrue(prd_path.is_file())
            content = prd_path.read_text()
            self.assertIn("project: openclaw", content)
            self.assertIn("# Test PRD", content)


class TestProvisionKnowledgeFailures(unittest.TestCase):
    """Each helper failure surfaces HelperError with helper name."""

    def _setup(self, td):
        bk = Path(td) / "bk"
        bk.mkdir()
        _fake_skill_lib(bk)
        wt = Path(td) / "wt"
        wt.mkdir()
        return bk, wt

    def test_slot_resolve_failure_raises(self):
        with tempfile.TemporaryDirectory() as td:
            bk, _ = self._setup(td)

            def fake_run(cmd, **kwargs):
                helper = Path(cmd[1]).name
                if helper == "slot_resolve.sh":
                    return MagicMock(
                        returncode=1, stdout="",
                        stderr="error: 'foo' is non-canonical",
                    )
                raise AssertionError("should fail before " + helper)

            with patch(
                "lib.provisioners._helpers.subprocess.run",
                side_effect=fake_run,
            ):
                with self.assertRaises(HelperError) as ctx:
                    provision_knowledge("foo", bk_path=bk)
            self.assertEqual(ctx.exception.helper, "slot_resolve")
            self.assertEqual(ctx.exception.exit_code, 1)
            self.assertIn("non-canonical", ctx.exception.stderr)

    def test_git_open_draft_failure_raises(self):
        with tempfile.TemporaryDirectory() as td:
            bk, _ = self._setup(td)

            def fake_run(cmd, **kwargs):
                helper = Path(cmd[1]).name
                if helper == "slot_resolve.sh":
                    return MagicMock(returncode=0, stdout="", stderr="")
                if helper == "git_open_draft.sh":
                    return MagicMock(
                        returncode=1, stdout="",
                        stderr="error: branch already exists",
                    )
                raise AssertionError(helper)

            with patch(
                "lib.provisioners._helpers.subprocess.run",
                side_effect=fake_run,
            ):
                with self.assertRaises(HelperError) as ctx:
                    provision_knowledge("openclaw", bk_path=bk)
            self.assertEqual(ctx.exception.helper, "git_open_draft")
            self.assertIn("branch already exists", ctx.exception.stderr)

    def test_commit_push_failure_raises_after_folders_created(self):
        with tempfile.TemporaryDirectory() as td:
            bk, wt = self._setup(td)

            def fake_run(cmd, **kwargs):
                helper = Path(cmd[1]).name
                if helper == "slot_resolve.sh":
                    return MagicMock(returncode=0, stdout="", stderr="")
                if helper == "git_open_draft.sh":
                    return MagicMock(returncode=0, stdout=f"{wt}\n", stderr="")
                if helper == "git_commit_push.sh":
                    return MagicMock(
                        returncode=1, stdout="",
                        stderr="error: push rejected",
                    )
                raise AssertionError(helper)

            with patch(
                "lib.provisioners._helpers.subprocess.run",
                side_effect=fake_run,
            ):
                with self.assertRaises(HelperError) as ctx:
                    provision_knowledge("openclaw", bk_path=bk)
            self.assertEqual(ctx.exception.helper, "git_commit_push")
            # Folders were already created in the worktree before push
            for folder in CANONICAL_FOLDERS:
                self.assertTrue((wt / folder / "openclaw").is_dir())


class TestProvisionKnowledgeMissingPaths(unittest.TestCase):
    """Fail-loud when bevox-knowledge or skill lib is absent."""

    def test_missing_bk_dir_raises_filenotfound(self):
        with tempfile.TemporaryDirectory() as td:
            bk = Path(td) / "missing"
            with self.assertRaises(FileNotFoundError) as ctx:
                provision_knowledge("openclaw", bk_path=bk)
            self.assertIn("bevox-knowledge", str(ctx.exception))

    def test_missing_skill_lib_raises_filenotfound(self):
        with tempfile.TemporaryDirectory() as td:
            bk = Path(td) / "bk"
            bk.mkdir()
            # Do not create the skill lib subtree.
            with self.assertRaises(FileNotFoundError) as ctx:
                provision_knowledge("openclaw", bk_path=bk)
            self.assertIn("skill helpers not found", str(ctx.exception))


class TestProvisionKnowledgeBkPathResolution(unittest.TestCase):
    """Default resolution honors BEVOX_KNOWLEDGE_DIR > BEVOX_KNOWLEDGE_PATH > ~/bevox-knowledge."""

    def test_uses_env_var(self):
        with tempfile.TemporaryDirectory() as td:
            bk = Path(td) / "bk"
            bk.mkdir()
            _fake_skill_lib(bk)
            wt = Path(td) / "wt"
            wt.mkdir()

            def fake_run(cmd, **kwargs):
                helper = Path(cmd[1]).name
                if helper == "slot_resolve.sh":
                    return MagicMock(returncode=0, stdout="", stderr="")
                if helper == "git_open_draft.sh":
                    return MagicMock(returncode=0, stdout=f"{wt}\n", stderr="")
                if helper == "git_commit_push.sh":
                    return MagicMock(returncode=0, stdout="h\nu\n", stderr="")
                raise AssertionError(helper)

            with patch.dict(
                os.environ,
                {"BEVOX_KNOWLEDGE_DIR": str(bk)},
                clear=False,
            ):
                with patch(
                    "lib.provisioners._helpers.subprocess.run",
                    side_effect=fake_run,
                ):
                    result = provision_knowledge("openclaw")
            self.assertEqual(result.state, "provisioned")


class TestProvisionKnowledgeRerunWithExistingBranch(unittest.TestCase):
    """Per spec decision (a): rerun with branch present surfaces helper error.

    No auto-recovery in W2; W5 doctor handles drift.
    """

    def test_rerun_when_branch_exists_raises_helper_error(self):
        with tempfile.TemporaryDirectory() as td:
            bk = Path(td) / "bk"
            bk.mkdir()
            _fake_skill_lib(bk)

            def fake_run(cmd, **kwargs):
                helper = Path(cmd[1]).name
                if helper == "slot_resolve.sh":
                    return MagicMock(returncode=0, stdout="", stderr="")
                if helper == "git_open_draft.sh":
                    return MagicMock(
                        returncode=1, stdout="",
                        stderr=(
                            "error: branch 'draft/openclaw-knowledge-bootstrap' "
                            "already exists; pick a new name or git branch -D"
                        ),
                    )
                raise AssertionError(helper)

            with patch(
                "lib.provisioners._helpers.subprocess.run",
                side_effect=fake_run,
            ):
                with self.assertRaises(HelperError) as ctx:
                    provision_knowledge("openclaw", bk_path=bk)
            self.assertIn("already exists", ctx.exception.stderr)


if __name__ == "__main__":
    unittest.main()
