"""Tests for `openclaw project status` CLI handler (W3).

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w3-v1.md
"""
import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from lib import api


def _build_meta_with_two_projects() -> dict:
    """projects-meta.json fixture with one provisioned + one drifted project."""
    return {
        "version": 1,
        "projects": {
            "alpha": {
                "name": "Alpha",
                "source": "user_created",
                "created_at": "2026-04-15T00:00:00Z",
                "bot_id": "alpha",
                "bot_port": 18000,
                "telegram": {"topics": {
                    "clarifications": 1, "dispatcher": 2, "blocks": 3,
                }},
                "capabilities_schema_version": 1,
                "capabilities": {
                    "code_repo": {"state": "provisioned"},
                    "knowledge_slot": {"state": "provisioned"},
                    "kanban_sprints": {"state": "provisioned"},
                    "workspace": {"state": "provisioned"},
                    "persona": {"state": "provisioned"},
                    "bot": {"state": "provisioned"},
                    "telegram_topics": {"state": "provisioned"},
                    "mission_control": {"state": "absent"},
                },
            },
            "beta": {
                "name": "Beta",
                "source": "adopted",
                "created_at": "2026-04-20T00:00:00Z",
                "bot_id": None,
                "telegram": {"topics": {}},
                "capabilities_schema_version": 1,
                "capabilities": {
                    # Declared partial → if detect returns absent, drift surfaces.
                    "code_repo": {"state": "partial"},
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
    }


def _make_args(**overrides) -> argparse.Namespace:
    """argparse.Namespace mirroring `project status` parser defaults."""
    base = dict(
        slug=None, no_detect=True, skip_remote=True, skip_systemctl=True,
        skip_knowledge=True, json=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class TestCmdProjectStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.openclaw_dir = Path(self._tmp.name) / "openclaw"
        self.openclaw_dir.mkdir(parents=True)
        self.code_dir = Path(self._tmp.name) / "code"
        self.code_dir.mkdir(parents=True)
        self.kb_dir = Path(self._tmp.name) / "kb"
        self.kb_dir.mkdir(parents=True)

        self.meta_path = self.openclaw_dir / "projects-meta.json"
        self.meta_path.write_text(json.dumps(_build_meta_with_two_projects()))

        self._env_patch = patch.dict(os.environ, {
            "OPENCLAW_DIR": str(self.openclaw_dir),
            "BEVOX_CODE_DIR": str(self.code_dir),
            "BEVOX_KNOWLEDGE_DIR": str(self.kb_dir),
        })
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()
        self._tmp.cleanup()

    def _capture_stdout(self, args) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = api.cmd_project_status(args)
        return rc, buf.getvalue()

    # ------- single project mode -------

    def test_single_project_renders_human_table(self):
        args = _make_args(slug="alpha")
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        self.assertIn("Project: alpha", out)
        self.assertIn("Capability", out)
        self.assertIn("Summary", out)
        # All 8 capabilities listed.
        for cap in ("code_repo", "knowledge_slot", "kanban_sprints",
                    "workspace", "persona", "bot", "telegram_topics",
                    "mission_control"):
            self.assertIn(cap, out)

    def test_single_project_not_found_returns_64(self):
        args = _make_args(slug="ghost")
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 64)
        self.assertIn("ghost", out)
        self.assertIn("not found", out)

    def test_single_project_not_found_json(self):
        args = _make_args(slug="ghost", json=True)
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 64)
        payload = json.loads(out.strip())
        self.assertEqual(payload["error"], "project_not_found")
        self.assertEqual(payload["slug"], "ghost")

    # ------- dispatcher mode -------

    def test_dispatcher_table_has_both_projects(self):
        args = _make_args(slug=None)
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        self.assertIn("alpha", out)
        self.assertIn("beta", out)
        # Header shows short codes.
        self.assertIn("code", out)
        self.assertIn("know", out)

    def test_dispatcher_alphabetical_ordering(self):
        args = _make_args(slug=None)
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        self.assertLess(out.find("alpha"), out.find("beta"))

    # ------- JSON contract -------

    def test_json_output_valid_and_has_schema_version(self):
        args = _make_args(slug=None, json=True)
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        # Should be a single JSON document on stdout.
        payload = json.loads(out.strip())
        self.assertEqual(payload["schema_version"], 1)
        self.assertIn("generated_at", payload)
        self.assertIn("alpha", payload["projects"])
        self.assertIn("beta", payload["projects"])
        # Spec: each capability has declared/detected/drift fields.
        alpha_caps = payload["projects"]["alpha"]["capabilities"]
        for cap in alpha_caps.values():
            self.assertIn("declared", cap)
            self.assertIn("detected", cap)
            self.assertIn("drift", cap)

    def test_json_no_detect_sets_detected_null(self):
        args = _make_args(slug=None, json=True, no_detect=True)
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        self.assertTrue(payload["detect_skipped"])
        for proj in payload["projects"].values():
            for cap in proj["capabilities"].values():
                self.assertIsNone(cap["detected"])
                self.assertFalse(cap["drift"])

    # ------- detect drift -------

    def test_drift_surfaces_when_declared_provisioned_but_detected_absent(self):
        # alpha declares all provisioned; with skip flags + empty fixture dirs,
        # detect_all returns absent for most. Drifts should show in JSON.
        args = _make_args(
            slug="alpha", no_detect=False, json=True,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
        )
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        proj = payload["projects"]["alpha"]
        # At least code_repo and workspace should drift (declared provisioned,
        # detected absent because dirs don't exist in fixture).
        self.assertIn("code_repo", proj["drifts"])
        self.assertIn("workspace", proj["drifts"])
        # mission_control declared absent + detected absent → no drift.
        self.assertNotIn("mission_control", proj["drifts"])

    def test_drift_marker_in_human_render(self):
        args = _make_args(
            slug="alpha", no_detect=False,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
        )
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        self.assertIn("DRIFT", out)
        # Summary line counts at least one drift.
        # Extract the "Summary:" line and verify drift count > 0.
        summary_line = [
            ln for ln in out.splitlines() if "Summary:" in ln
        ][0]
        self.assertNotIn("0 drift", summary_line)

    # ------- skip flags propagate -------

    def test_skip_flags_propagate_to_detect_all(self):
        seen: dict = {}

        def fake_detect_all(slug, paths, meta_entry=None, **kwargs):
            seen.update(kwargs)
            return {cap: {"state": "absent"} for cap in (
                "code_repo", "knowledge_slot", "kanban_sprints",
                "workspace", "persona", "bot", "telegram_topics",
                "mission_control",
            )}

        args = _make_args(
            slug="alpha", no_detect=False,
            skip_remote=True, skip_systemctl=True, skip_knowledge=True,
        )
        with patch("lib.capability_detect.detect_all", side_effect=fake_detect_all):
            rc, _ = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        self.assertTrue(seen.get("skip_remote"))
        self.assertTrue(seen.get("skip_systemctl"))
        self.assertTrue(seen.get("skip_knowledge"))

    # ------- no-detect short-circuits detect_all -------

    def test_no_detect_does_not_call_detect_all(self):
        called = {"flag": False}

        def fake_detect_all(*a, **kw):
            called["flag"] = True
            return {}

        args = _make_args(slug="alpha", no_detect=True)
        with patch("lib.capability_detect.detect_all", side_effect=fake_detect_all):
            rc, _ = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        self.assertFalse(called["flag"])

    # ------- empty meta -------

    def test_dispatcher_empty_meta(self):
        self.meta_path.write_text(json.dumps({"version": 1, "projects": {}}))
        args = _make_args(slug=None)
        rc, out = self._capture_stdout(args)
        self.assertEqual(rc, 0)
        self.assertIn("no projects", out)


class TestParserWiring(unittest.TestCase):
    """Verify build_parser actually registers `project status` subcommand."""

    def test_project_status_subcommand_registered(self):
        parser = api.build_parser()
        # parse a no-detect run and check func is bound.
        args = parser.parse_args(["project", "status", "--no-detect"])
        self.assertIs(args.func, api.cmd_project_status)
        self.assertIsNone(args.slug)
        self.assertTrue(args.no_detect)

    def test_project_status_with_slug(self):
        parser = api.build_parser()
        args = parser.parse_args(["project", "status", "foo"])
        self.assertEqual(args.slug, "foo")
        self.assertFalse(args.no_detect)

    def test_project_status_skip_flags(self):
        parser = api.build_parser()
        args = parser.parse_args([
            "project", "status",
            "--skip-remote", "--skip-systemctl", "--skip-knowledge",
        ])
        self.assertTrue(args.skip_remote)
        self.assertTrue(args.skip_systemctl)
        self.assertTrue(args.skip_knowledge)

    def test_project_status_json_flag(self):
        # `--json` is a per-leaf flag (parents=[common]), so it lives after
        # the leaf subcommand: `project status --json`.
        parser = api.build_parser()
        args = parser.parse_args(["project", "status", "--json"])
        self.assertTrue(args.json)


if __name__ == "__main__":
    unittest.main()
