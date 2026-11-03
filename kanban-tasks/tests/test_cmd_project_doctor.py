"""Tests for `openclaw project doctor` (W5 cross-project drift CLI).

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w5-v1.md
"""
import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lib.cli.cmd_project_doctor import cmd_project_doctor


def _make_args(**overrides) -> argparse.Namespace:
    base = dict(
        fix=False,
        auto_confirm=False,
        json=False,
        skip_orphans=False,
        include=None,
        exclude=None,
        skip_remote=True,
        skip_systemctl=True,
        skip_knowledge=True,
        actor="bernard",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class _DoctorBase(unittest.TestCase):

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
        self.meta_path.write_text(json.dumps(
            {"version": 1, "projects": {}}, indent=2,
        ))

        self._env = patch.dict(os.environ, {
            "OPENCLAW_DIR": str(self.openclaw_dir),
            "BEVOX_KNOWLEDGE_DIR": str(self.kb_dir),
            "BEVOX_CODE_DIR": str(self.code_dir),
            "HOME": str(self.home),
        })
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def _seed_project(self, slug, capabilities, **extra):
        meta = json.loads(self.meta_path.read_text())
        entry = {
            "name": slug,
            "source": "user_created",
            "bot_id": None,
            "telegram": {"topics": {}},
            "capabilities_schema_version": 1,
            "capabilities": capabilities,
        }
        entry.update(extra)
        meta["projects"][slug] = entry
        self.meta_path.write_text(json.dumps(meta, indent=2))

    def _all_absent(self):
        return {
            n: {"state": "absent"} for n in (
                "code_repo", "knowledge_slot", "kanban_sprints",
                "workspace", "persona", "bot",
                "telegram_topics", "mission_control",
            )
        }

    def _run(self, args) -> tuple:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_project_doctor(args)
        return rc, buf.getvalue()


class TestEmptyMeta(_DoctorBase):

    def test_empty_meta_exits_ok(self):
        args = _make_args(json=True, skip_orphans=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["projects"], {})
        self.assertEqual(payload["summary"]["projects_scanned"], 0)
        self.assertEqual(payload["summary"]["total_drifts"], 0)


class TestAllClean(_DoctorBase):

    def test_no_drift_when_all_caps_absent_and_detected_absent(self):
        self._seed_project("alpha", self._all_absent())
        args = _make_args(json=True, skip_orphans=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["total_drifts"], 0)
        self.assertEqual(payload["projects"]["alpha"]["drifts"], [])


class TestSingleDrift(_DoctorBase):

    def test_single_drift_detected(self):
        caps = self._all_absent()
        caps["code_repo"] = {"state": "provisioned"}
        # No code dir → detect=absent → drift.
        self._seed_project("alpha", caps)
        args = _make_args(json=True, skip_orphans=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertIn("code_repo", payload["projects"]["alpha"]["drifts"])
        self.assertEqual(payload["summary"]["total_drifts"], 1)
        self.assertEqual(payload["summary"]["projects_with_drift"], 1)


class TestMultipleDrifts(_DoctorBase):

    def test_multiple_drifts_across_projects(self):
        caps_a = self._all_absent()
        caps_a["code_repo"] = {"state": "provisioned"}
        caps_a["workspace"] = {"state": "provisioned"}
        self._seed_project("alpha", caps_a)
        caps_b = self._all_absent()
        caps_b["persona"] = {"state": "provisioned"}
        self._seed_project("beta", caps_b)
        args = _make_args(json=True, skip_orphans=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["projects_with_drift"], 2)
        self.assertGreaterEqual(payload["summary"]["total_drifts"], 3)


class TestOrphanDetection(_DoctorBase):

    def test_orphan_dir_reported_not_removed(self):
        self._seed_project("alpha", self._all_absent())
        # Orphan code dir.
        (self.code_dir / "ghost" / ".git").mkdir(parents=True)
        # Orphan bot profile.
        (self.home / ".openclaw-orphan").mkdir()
        args = _make_args(json=True, skip_orphans=False)
        # Skip drafts to avoid hitting git.
        # We can't pass skip_drafts to args directly since CLI gates both via
        # skip_orphans; test scanner-level coverage in test_doctor_scanner.
        # Here just run with skip_orphans=False; but need to mock subprocess
        # for drafts. Easier: assert the orphans listed and ignore drafts list.
        with patch(
            "lib.doctor.scanner._run_cmd",
            return_value=(128, "", "no remote"),
        ):
            rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        # Orphan code dir present (not removed).
        self.assertEqual(len(payload["orphans"]["code_dirs"]), 1)
        self.assertTrue(payload["orphans"]["code_dirs"][0].endswith("ghost"))
        self.assertEqual(len(payload["orphans"]["bot_profiles"]), 1)
        # Orphan dir still exists on disk.
        self.assertTrue((self.code_dir / "ghost").is_dir())


class TestFixAutoConfirm(_DoctorBase):

    def test_fix_with_inverse_drift_writes_meta(self):
        # Declared absent, but workspace dir exists → detect=provisioned →
        # inverse drift. --fix --auto-confirm should sync meta to provisioned.
        self._seed_project("alpha", self._all_absent())
        ws = self.openclaw_dir / "workspace-alpha"
        ws.mkdir()
        (ws / "IDENTITY.md").write_text(
            "---\npersona_status: generated\n---\n"
        )
        args = _make_args(
            fix=True, auto_confirm=True, json=True, skip_orphans=True,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        # workspace drift was repaired.
        ws_repair = next(
            (r for r in payload.get("repairs", []) if r["capability"] == "workspace"),
            None,
        )
        self.assertIsNotNone(ws_repair)
        self.assertEqual(ws_repair["action"], "repaired")
        # Meta now declares workspace=provisioned.
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(
            meta["projects"]["alpha"]["capabilities"]["workspace"]["state"],
            "provisioned",
        )

    def test_fix_idempotent_rerun_is_noop(self):
        # Setup so detect matches declared → no drifts → repair list empty.
        self._seed_project("alpha", self._all_absent())
        args = _make_args(
            fix=True, auto_confirm=True, json=True, skip_orphans=True,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["total_drifts"], 0)
        self.assertEqual(payload.get("repairs", []), [])


class TestSkipFlags(_DoctorBase):

    def test_skip_orphans_flag_works(self):
        self._seed_project("alpha", self._all_absent())
        (self.code_dir / "ghost" / ".git").mkdir(parents=True)
        args = _make_args(json=True, skip_orphans=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["orphans"]["code_dirs"], [])
        self.assertEqual(payload["drafts_pending"], [])


class TestFixRequiresTtyOrAutoConfirm(_DoctorBase):

    def test_fix_no_tty_no_auto_confirm_exits_64(self):
        self._seed_project("alpha", self._all_absent())
        args = _make_args(
            fix=True, auto_confirm=False, json=True, skip_orphans=True,
        )
        # stdin.isatty defaults to False in test → exit 64.
        with patch("sys.stdin.isatty", return_value=False):
            rc, out = self._run(args)
        self.assertEqual(rc, 64)
        payload = json.loads(out)
        self.assertEqual(payload["error"], "fix_requires_tty_or_auto_confirm")


class TestHumanRender(_DoctorBase):

    def test_human_renders_summary(self):
        self._seed_project("alpha", self._all_absent())
        args = _make_args(json=False, skip_orphans=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        self.assertIn("Project doctor scan", out)
        self.assertIn("Summary:", out)
        self.assertIn("alpha", out)


class TestIncludeExclude(_DoctorBase):

    def test_include_filters(self):
        self._seed_project("alpha", self._all_absent())
        self._seed_project("beta", self._all_absent())
        args = _make_args(
            json=True, skip_orphans=True, include="alpha",
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(set(payload["projects"].keys()), {"alpha"})


if __name__ == "__main__":
    unittest.main()
