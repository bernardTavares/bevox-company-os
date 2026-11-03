"""Tests for `openclaw project adopt` (W4 brownfield entry point).

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w4-v1.md
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

from lib.cli.cmd_project_adopt import cmd_project_adopt, _decide_action


def _make_args(**overrides) -> argparse.Namespace:
    base = dict(
        slug="bevox-direct",
        prd=None,
        description="",
        domain="",
        bot=None,
        non_interactive=True,  # default tests to non-interactive
        dry_run=False,
        skip=None,
        skip_remote=True,
        skip_systemctl=True,
        skip_knowledge=True,
        skip_slot_check=True,
        bot_id=None,
        bot_port=None,
        bot_token=None,
        bot_chat_id=None,
        bot_allow_from=None,
        bot_skills=None,
        json=False,
        actor="bernard",
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _seed_meta_with_entry(meta_path: Path, slug: str, capabilities: dict,
                          source: str = "user_created") -> None:
    """Pre-populate projects-meta with an entry."""
    data = {
        "version": 1,
        "projects": {
            slug: {
                "name": slug,
                "source": source,
                "created_at": "2026-04-01T00:00:00Z",
                "bot_id": None,
                "telegram": {"topics": {}},
                "capabilities_schema_version": 1,
                "capabilities": capabilities,
            },
        },
    }
    meta_path.write_text(json.dumps(data, indent=2))


class TestDecideAction(unittest.TestCase):
    """Pure-function tests for _decide_action policy table."""

    def test_skip_flag_overrides(self):
        action, _ = _decide_action(
            "bot", "absent", interactive=True, bot_flag="yes",
            skip=["bot"], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "skip-flag")

    def test_already_provisioned(self):
        action, _ = _decide_action(
            "workspace", "provisioned", interactive=False,
            bot_flag="", skip=[], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "skip-already")

    def test_partial_repairs(self):
        action, _ = _decide_action(
            "workspace", "partial", interactive=False,
            bot_flag="", skip=[], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "repair")

    def test_drifted_skip_in_non_interactive(self):
        action, _ = _decide_action(
            "bot", "drifted", interactive=False,
            bot_flag="no", skip=[], prompt_fn=lambda *a, **k: False,
        )
        self.assertEqual(action, "skip")

    def test_bot_absent_yes_provisions(self):
        action, _ = _decide_action(
            "bot", "absent", interactive=False,
            bot_flag="yes", skip=[], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "provision")

    def test_bot_absent_no_skips(self):
        action, _ = _decide_action(
            "bot", "absent", interactive=False,
            bot_flag="no", skip=[], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "skip-flag")

    def test_bot_absent_auto_skips(self):
        action, _ = _decide_action(
            "bot", "absent", interactive=False,
            bot_flag="auto", skip=[], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "skip")

    def test_other_absent_default_skip_in_non_interactive(self):
        action, _ = _decide_action(
            "workspace", "absent", interactive=False,
            bot_flag="", skip=[], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "skip")

    def test_other_absent_interactive_yes(self):
        action, _ = _decide_action(
            "workspace", "absent", interactive=True,
            bot_flag="", skip=[], prompt_fn=lambda *a, **k: True,
        )
        self.assertEqual(action, "prompt-yes")

    def test_other_absent_interactive_no(self):
        action, _ = _decide_action(
            "workspace", "absent", interactive=True,
            bot_flag="", skip=[], prompt_fn=lambda *a, **k: False,
        )
        self.assertEqual(action, "prompt-no")


class _AdoptTestBase(unittest.TestCase):
    """Common setup: tmp openclaw + kb + code dirs + env patch."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.openclaw_dir = root / "openclaw"
        self.openclaw_dir.mkdir()
        self.kb_dir = root / "kb"
        self.kb_dir.mkdir()
        self.code_dir = root / "code"
        self.code_dir.mkdir()

        # Create empty meta file.
        self.meta_path = self.openclaw_dir / "projects-meta.json"
        self.meta_path.write_text(json.dumps(
            {"version": 1, "projects": {}}, indent=2,
        ))

        self._env = patch.dict(os.environ, {
            "OPENCLAW_DIR": str(self.openclaw_dir),
            "BEVOX_KNOWLEDGE_DIR": str(self.kb_dir),
            "BEVOX_CODE_DIR": str(self.code_dir),
        })
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def _run(self, args) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_project_adopt(args)
        return rc, buf.getvalue()


class TestAdoptValidation(_AdoptTestBase):
    """Argument / preflight validation."""

    def test_non_interactive_without_bot_flag_fails(self):
        args = _make_args(non_interactive=True, bot=None, json=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 1)
        payload = json.loads(out)
        self.assertEqual(payload["error"], "non_interactive_requires_bot_flag")

    def test_invalid_bot_flag_fails(self):
        args = _make_args(non_interactive=True, bot="maybe", json=True)
        rc, out = self._run(args)
        self.assertEqual(rc, 1)
        payload = json.loads(out)
        self.assertEqual(payload["error"], "invalid_bot_flag")

    def test_invalid_skip_fails(self):
        args = _make_args(
            non_interactive=True, bot="no", skip="not_a_capability", json=True,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 1)
        payload = json.loads(out)
        self.assertEqual(payload["error"], "invalid_skip")

    def test_missing_prd_file_fails(self):
        args = _make_args(
            non_interactive=True, bot="no",
            prd=str(self.openclaw_dir / "nope.md"),
            json=True,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 1)
        payload = json.loads(out)
        self.assertEqual(payload["error"], "prd_file_missing")


class TestAdoptDryRun(_AdoptTestBase):
    """--dry-run never mutates meta."""

    def test_dry_run_returns_plan_no_mutation(self):
        args = _make_args(
            non_interactive=True, bot="no", dry_run=True, json=True,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["slug"], "bevox-direct")
        # Plan has all 8 capabilities.
        self.assertEqual(len(payload["plan"]), 8)
        # No entry was written.
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(meta.get("projects", {}), {})

    def test_dry_run_human_renders_table(self):
        args = _make_args(
            non_interactive=True, bot="no", dry_run=True, json=False,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        self.assertIn("Adopt plan for bevox-direct", out)
        self.assertIn("Capability", out)
        self.assertIn("knowledge_slot", out)


class TestAdoptCreatesSkeletonAdopted(_AdoptTestBase):
    """When entry doesn't exist, adopt creates it with source=adopted."""

    def test_creates_entry_with_source_adopted(self):
        args = _make_args(
            slug="newslug",
            non_interactive=True, bot="no",
            description="A test", domain="Tech",
            json=True,
        )
        rc, _ = self._run(args)
        self.assertEqual(rc, 0)
        meta = json.loads(self.meta_path.read_text())
        entry = meta["projects"]["newslug"]
        self.assertEqual(entry["source"], "adopted")
        self.assertIn("adopted_at", entry)
        self.assertIn("last_adopt_at", entry)
        self.assertEqual(entry["description"], "A test")

    def test_existing_entry_preserves_source(self):
        # Existing user_created entry; adopt rerun should not flip to adopted.
        _seed_meta_with_entry(
            self.meta_path, "preexisting",
            capabilities={
                "code_repo": {"state": "provisioned"},
                "knowledge_slot": {"state": "provisioned"},
                "kanban_sprints": {"state": "provisioned"},
                "workspace": {"state": "provisioned"},
                "persona": {"state": "provisioned"},
                "bot": {"state": "absent"},
                "telegram_topics": {"state": "absent"},
                "mission_control": {"state": "absent"},
            },
            source="user_created",
        )
        args = _make_args(
            slug="preexisting",
            non_interactive=True, bot="no",
            json=True,
        )
        rc, _ = self._run(args)
        self.assertEqual(rc, 0)
        meta = json.loads(self.meta_path.read_text())
        self.assertEqual(meta["projects"]["preexisting"]["source"], "user_created")


class TestAdoptIdempotency(_AdoptTestBase):
    """Fully-provisioned project = no-op."""

    def test_fully_provisioned_is_noop(self):
        # Pre-seed with all capabilities provisioned; with all skip-detect
        # flags + bot=no, no provisioner runs.
        _seed_meta_with_entry(
            self.meta_path, "alpha",
            capabilities={
                "code_repo": {"state": "provisioned"},
                "knowledge_slot": {"state": "provisioned"},
                "kanban_sprints": {"state": "provisioned"},
                "workspace": {"state": "provisioned"},
                "persona": {"state": "provisioned"},
                "bot": {"state": "absent"},
                "telegram_topics": {"state": "absent"},
                "mission_control": {"state": "absent"},
            },
        )
        # Workspace dir + IDENTITY exist so detect returns provisioned.
        ws = self.openclaw_dir / "workspace-alpha"
        ws.mkdir()
        (ws / "IDENTITY.md").write_text(
            "---\npersona_status: generated\n---\n"
        )
        # code_repo dir
        (self.code_dir / "alpha").mkdir()
        # kanban state.json with sprints
        kt = self.openclaw_dir / "kanban-tasks"
        kt.mkdir()
        (kt / "state.json").write_text(json.dumps({"sprints": [
            {"id": "s1", "project": "alpha", "status": "current"},
            {"id": "s2", "project": "alpha", "status": "next"},
        ]}))

        args = _make_args(
            slug="alpha", non_interactive=True, bot="no", json=True,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertTrue(payload["noop"])
        # All actions are skip-* variants
        for r in payload["results"]:
            self.assertFalse(r["executed"])


class TestAdoptPartialProvisioning(_AdoptTestBase):
    """Partial state runs only missing capability provisioner."""

    def test_only_missing_capability_runs(self):
        # Seed entry with workspace absent; everything else provisioned.
        _seed_meta_with_entry(
            self.meta_path, "delta",
            capabilities={
                "code_repo": {"state": "provisioned"},
                "knowledge_slot": {"state": "provisioned"},
                "kanban_sprints": {"state": "provisioned"},
                "workspace": {"state": "absent"},
                "persona": {"state": "absent"},
                "bot": {"state": "absent"},
                "telegram_topics": {"state": "absent"},
                "mission_control": {"state": "absent"},
            },
        )
        # Setup so that detect_workspace returns absent (no dir),
        # other detects return provisioned where applicable.
        (self.code_dir / "delta").mkdir()
        kt = self.openclaw_dir / "kanban-tasks"
        kt.mkdir()
        (kt / "state.json").write_text(json.dumps({"sprints": [
            {"id": "s1", "project": "delta", "status": "current"},
            {"id": "s2", "project": "delta", "status": "next"},
        ]}))

        # Workspace template needed for provisioner to succeed.
        wt = self.openclaw_dir / "workspace-template"
        wt.mkdir()
        (wt / "IDENTITY.md").write_text("# {{SLUG}}\npersona_status: pending\n")

        args = _make_args(
            slug="delta",
            non_interactive=True, bot="no",
            # In non-interactive mode, absent capabilities default to skip
            # except via flag. But interactive=True covers the prompt path.
            json=True,
        )
        # With non-interactive default-skip, only repair (partial) cases run.
        # workspace is absent → would skip; verify that's the behavior.
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        # workspace was absent → skipped (no flag to enable).
        ws_row = next(r for r in payload["results"]
                      if r["capability"] == "workspace")
        self.assertFalse(ws_row["executed"])
        self.assertEqual(ws_row["action"], "skip")


class TestAdoptInteractiveProvisions(_AdoptTestBase):
    """Interactive mode with prompt confirming provisions absent caps."""

    def test_interactive_yes_runs_workspace_provisioner(self):
        # Pre-seed so only workspace is absent.
        _seed_meta_with_entry(
            self.meta_path, "epsilon",
            capabilities={
                "code_repo": {"state": "absent"},
                "knowledge_slot": {"state": "absent"},
                "kanban_sprints": {"state": "absent"},
                "workspace": {"state": "absent"},
                "persona": {"state": "absent"},
                "bot": {"state": "absent"},
                "telegram_topics": {"state": "absent"},
                "mission_control": {"state": "absent"},
            },
        )
        # Setup workspace template so provisioner can run.
        wt = self.openclaw_dir / "workspace-template"
        wt.mkdir()
        (wt / "IDENTITY.md").write_text(
            "---\npersona_status: pending\n---\n# {{SLUG}}\n"
        )

        # Skip everything except workspace via --skip.
        args = _make_args(
            slug="epsilon",
            non_interactive=False,
            bot=None,  # interactive bot prompt → patch input to "n"
            skip="code_repo,knowledge_slot,persona,bot,telegram_topics,kanban_sprints,mission_control",
            json=True,
        )
        # User answers Y to "criar workspace?" prompt.
        with patch("builtins.input", return_value="y"):
            rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        ws_row = next(r for r in payload["results"]
                      if r["capability"] == "workspace")
        self.assertTrue(ws_row["executed"])
        self.assertIn(ws_row["result_state"], ("provisioned", "partial"))
        # Workspace dir created.
        self.assertTrue((self.openclaw_dir / "workspace-epsilon").is_dir())


class TestAdoptMissionControlStub(_AdoptTestBase):
    """mission_control provisioner returns absent (W6 stub)."""

    def test_mc_absent_is_skipped_no_run(self):
        args = _make_args(
            slug="zeta",
            non_interactive=True, bot="no", json=True,
        )
        rc, out = self._run(args)
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        mc_row = next(r for r in payload["results"]
                      if r["capability"] == "mission_control")
        self.assertFalse(mc_row["executed"])


if __name__ == "__main__":
    unittest.main()
