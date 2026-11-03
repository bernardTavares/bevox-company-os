"""Tests for lib.doctor.scanner — drift, orphan, drafts detection.

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w5-v1.md
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.capability_detect import DetectPaths
from lib.doctor.scanner import (
    detect_drafts_pending,
    detect_drifts_for_slug,
    detect_orphan_bot_profiles,
    detect_orphan_code_dirs,
    detect_orphan_knowledge_slots,
    detect_orphan_workspaces,
    scan_all,
)


class _TmpEnv(unittest.TestCase):
    """Common tmp filesystem fixture."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.openclaw_dir = root / "openclaw"
        self.openclaw_dir.mkdir()
        self.kb_dir = root / "kb"
        self.kb_dir.mkdir()
        self.code_dir = root / "code"
        self.code_dir.mkdir()
        self.home = root / "home"
        self.home.mkdir()

        self.meta_path = self.openclaw_dir / "projects-meta.json"
        self._write_meta({"version": 1, "projects": {}})

        self.paths = DetectPaths(
            kb_dir=self.kb_dir, openclaw_dir=self.openclaw_dir,
            code_dir=self.code_dir, org="bernardTavares",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _write_meta(self, data):
        self.meta_path.write_text(json.dumps(data, indent=2))


class TestDetectDriftsForSlug(_TmpEnv):

    def test_no_drift_when_declared_matches_detected(self):
        entry = {
            "name": "alpha",
            "capabilities_schema_version": 1,
            "capabilities": {
                "code_repo": {"state": "absent"},
                "knowledge_slot": {"state": "absent"},
                "kanban_sprints": {"state": "absent"},
                "workspace": {"state": "absent"},
                "persona": {"state": "absent"},
                "bot": {"state": "absent"},
                "telegram_topics": {"state": "absent"},
                "mission_control": {"state": "absent"},
            },
        }
        # All detects will be 'absent' on this empty fixture (skip_knowledge
        # bypassed → 'skipped' → no drift).
        cap_payload, drifts = detect_drifts_for_slug(
            "alpha", self.paths, entry,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
        )
        self.assertEqual(drifts, [])
        # All capabilities present in payload.
        self.assertEqual(set(cap_payload.keys()), {
            "code_repo", "knowledge_slot", "kanban_sprints",
            "workspace", "persona", "bot", "telegram_topics", "mission_control",
        })

    def test_drift_when_declared_provisioned_but_detected_absent(self):
        entry = {
            "name": "alpha",
            "capabilities_schema_version": 1,
            "capabilities": {
                "code_repo": {"state": "provisioned"},
                "knowledge_slot": {"state": "absent"},
                "kanban_sprints": {"state": "absent"},
                "workspace": {"state": "absent"},
                "persona": {"state": "absent"},
                "bot": {"state": "absent"},
                "telegram_topics": {"state": "absent"},
                "mission_control": {"state": "absent"},
            },
        }
        # code_repo dir does NOT exist → detect=absent, declared=provisioned → drift.
        cap_payload, drifts = detect_drifts_for_slug(
            "alpha", self.paths, entry,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
        )
        drift_caps = [d.capability for d in drifts]
        self.assertIn("code_repo", drift_caps)
        self.assertEqual(cap_payload["code_repo"]["drift"], True)

    def test_drift_skipped_state_not_marked(self):
        entry = {
            "name": "alpha",
            "capabilities_schema_version": 1,
            "capabilities": {
                "knowledge_slot": {"state": "provisioned"},
                "code_repo": {"state": "absent"},
                "kanban_sprints": {"state": "absent"},
                "workspace": {"state": "absent"},
                "persona": {"state": "absent"},
                "bot": {"state": "absent"},
                "telegram_topics": {"state": "absent"},
                "mission_control": {"state": "absent"},
            },
        }
        _, drifts = detect_drifts_for_slug(
            "alpha", self.paths, entry,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
        )
        # knowledge_slot returns state=skipped → no drift.
        self.assertNotIn("knowledge_slot", [d.capability for d in drifts])


class TestOrphans(_TmpEnv):

    def test_orphan_code_dir(self):
        # Real project + orphan project, both with .git/.
        (self.code_dir / "alpha" / ".git").mkdir(parents=True)
        (self.code_dir / "legacy-foo" / ".git").mkdir(parents=True)
        # Without .git → ignored.
        (self.code_dir / "scratch").mkdir()
        out = detect_orphan_code_dirs(self.paths, declared_slugs={"alpha"})
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].endswith("legacy-foo"))

    def test_orphan_bot_profile(self):
        (self.home / ".openclaw").mkdir()  # blacklisted root install
        (self.home / ".openclaw-alpha").mkdir()  # declared
        (self.home / ".openclaw-deprecated").mkdir()  # orphan
        (self.home / "other-dir").mkdir()  # not a profile
        out = detect_orphan_bot_profiles(
            self.home, declared_bot_areas={"alpha"},
        )
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].endswith(".openclaw-deprecated"))

    def test_orphan_workspace(self):
        (self.openclaw_dir / "workspace-alpha").mkdir()
        (self.openclaw_dir / "workspace-orphan").mkdir()
        (self.openclaw_dir / "workspace-template").mkdir()  # excluded
        out = detect_orphan_workspaces(self.paths, declared_slugs={"alpha"})
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].endswith("workspace-orphan"))

    def test_orphan_knowledge_slot(self):
        # Two folders, each with one declared + one orphan + one excluded.
        (self.kb_dir / "00_inbox" / "alpha").mkdir(parents=True)
        (self.kb_dir / "00_inbox" / "ghost").mkdir()
        (self.kb_dir / "00_inbox" / "_shared").mkdir()
        (self.kb_dir / "30_adr" / "alpha").mkdir(parents=True)
        out = detect_orphan_knowledge_slots(self.paths, declared_slugs={"alpha"})
        self.assertEqual(out, ["00_inbox/ghost"])

    def test_orphan_handles_missing_dirs(self):
        # If kb_dir doesn't exist, returns [].
        bad = DetectPaths(
            kb_dir=Path("/nonexistent/path"),
            openclaw_dir=self.openclaw_dir,
            code_dir=self.code_dir,
        )
        self.assertEqual(detect_orphan_knowledge_slots(bad, set()), [])
        self.assertEqual(detect_orphan_code_dirs(bad, set()), [])


class TestDraftsPending(_TmpEnv):

    def test_drafts_returned_from_mock(self):
        def _mock_runner(cmd, cwd=None, timeout=10):
            stdout = (
                "abc123\trefs/heads/draft/bevox-site-knowledge-bootstrap\n"
                "def456\trefs/heads/draft/legacy-knowledge-bootstrap\n"
            )
            return 0, stdout, ""
        out = detect_drafts_pending(
            self.paths, declared_slugs={"bevox-site"},
            runner=_mock_runner,
        )
        self.assertEqual(len(out), 2)
        slugs = sorted([d.slug for d in out])
        self.assertEqual(slugs, ["bevox-site", "legacy"])

    def test_drafts_empty_on_git_failure(self):
        def _mock_runner(cmd, cwd=None, timeout=10):
            return 128, "", "fatal: not a git repository"
        out = detect_drafts_pending(
            self.paths, declared_slugs=set(),
            runner=_mock_runner,
        )
        self.assertEqual(out, [])


class TestScanAll(_TmpEnv):

    def test_empty_meta_returns_empty_scan(self):
        with patch.dict(os.environ, {"HOME": str(self.home)}):
            result = scan_all(
                self.meta_path, self.paths,
                skip_remote=True, skip_systemctl=True, skip_knowledge=True,
                skip_orphans=False, home=self.home,
            )
        self.assertEqual(result.projects, {})
        self.assertEqual(result.drifts, [])
        # No orphans to find.
        self.assertEqual(result.orphans.code_dirs, [])

    def test_scan_with_drift_and_orphan(self):
        self._write_meta({
            "version": 1,
            "projects": {
                "alpha": {
                    "name": "alpha",
                    "source": "user_created",
                    "capabilities_schema_version": 1,
                    "capabilities": {
                        "code_repo": {"state": "provisioned"},
                        "knowledge_slot": {"state": "absent"},
                        "kanban_sprints": {"state": "absent"},
                        "workspace": {"state": "absent"},
                        "persona": {"state": "absent"},
                        "bot": {"state": "absent"},
                        "telegram_topics": {"state": "absent"},
                        "mission_control": {"state": "absent"},
                    },
                },
            },
        })
        # code_repo dir doesn't exist → drift.
        # Orphan: a bot profile not declared.
        (self.home / ".openclaw-ghost").mkdir()
        # Skip drafts entirely so we don't hit git.
        result = scan_all(
            self.meta_path, self.paths,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
            skip_orphans=False, skip_drafts=True, home=self.home,
        )
        self.assertEqual(set(result.projects.keys()), {"alpha"})
        self.assertGreaterEqual(len(result.drifts), 1)
        self.assertTrue(any(d.capability == "code_repo" for d in result.drifts))
        self.assertEqual(len(result.orphans.bot_profiles), 1)

    def test_skip_orphans_returns_empty_orphan_report(self):
        self._write_meta({"version": 1, "projects": {}})
        (self.home / ".openclaw-ghost").mkdir()
        (self.code_dir / "ghost" / ".git").mkdir(parents=True)
        result = scan_all(
            self.meta_path, self.paths,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
            skip_orphans=True, home=self.home,
        )
        self.assertEqual(result.orphans.code_dirs, [])
        self.assertEqual(result.orphans.bot_profiles, [])
        self.assertEqual(result.drafts_pending, [])

    def test_include_filter_applies(self):
        self._write_meta({
            "version": 1,
            "projects": {
                "alpha": {
                    "name": "alpha", "capabilities_schema_version": 1,
                    "capabilities": {
                        n: {"state": "absent"} for n in (
                            "code_repo", "knowledge_slot", "kanban_sprints",
                            "workspace", "persona", "bot",
                            "telegram_topics", "mission_control",
                        )
                    },
                },
                "beta": {
                    "name": "beta", "capabilities_schema_version": 1,
                    "capabilities": {
                        n: {"state": "absent"} for n in (
                            "code_repo", "knowledge_slot", "kanban_sprints",
                            "workspace", "persona", "bot",
                            "telegram_topics", "mission_control",
                        )
                    },
                },
            },
        })
        result = scan_all(
            self.meta_path, self.paths,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
            skip_orphans=True, home=self.home,
            include=["alpha"],
        )
        self.assertEqual(set(result.projects.keys()), {"alpha"})

    def test_exclude_filter_applies(self):
        self._write_meta({
            "version": 1,
            "projects": {
                "alpha": {
                    "name": "alpha", "capabilities_schema_version": 1,
                    "capabilities": {
                        n: {"state": "absent"} for n in (
                            "code_repo", "knowledge_slot", "kanban_sprints",
                            "workspace", "persona", "bot",
                            "telegram_topics", "mission_control",
                        )
                    },
                },
                "beta": {
                    "name": "beta", "capabilities_schema_version": 1,
                    "capabilities": {
                        n: {"state": "absent"} for n in (
                            "code_repo", "knowledge_slot", "kanban_sprints",
                            "workspace", "persona", "bot",
                            "telegram_topics", "mission_control",
                        )
                    },
                },
            },
        })
        result = scan_all(
            self.meta_path, self.paths,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
            skip_orphans=True, home=self.home,
            exclude=["beta"],
        )
        self.assertEqual(set(result.projects.keys()), {"alpha"})


if __name__ == "__main__":
    unittest.main()
