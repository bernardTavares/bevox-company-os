"""Tests for capability detect helpers (pure runtime introspection).

Spec: bevox-knowledge/35_specs/openclaw/2026-05-07-project-lifecycle-w1-v1.md §Detect helpers
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib.capability_detect import (
    DetectPaths,
    detect_all,
    detect_bot,
    detect_code_repo,
    detect_kanban_sprints,
    detect_knowledge_slot,
    detect_mission_control,
    detect_persona,
    detect_telegram_topics,
    detect_workspace,
)


def _make_paths(td: str) -> DetectPaths:
    base = Path(td)
    return DetectPaths(
        kb_dir=base / "knowledge",
        openclaw_dir=base / "openclaw",
        code_dir=base / "code",
        org="bernardTavares",
    )


class TestDetectCodeRepo(unittest.TestCase):
    def test_absent_when_neither_local_nor_remote(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_code_repo("ghost", paths, skip_remote=True)
            self.assertEqual(r["state"], "absent")

    def test_provisioned_when_local_and_skip_remote(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            (paths.code_dir / "x").mkdir(parents=True)
            r = detect_code_repo("x", paths, skip_remote=True)
            self.assertEqual(r["state"], "provisioned")
            self.assertIn("github", r)

    def test_partial_when_local_no_github(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            (paths.code_dir / "x").mkdir(parents=True)
            with patch(
                "lib.capability_detect._run_cmd",
                return_value=(1, "", "Not Found"),
            ):
                r = detect_code_repo("x", paths)
            self.assertEqual(r["state"], "partial")
            self.assertIsNone(r["github"])

    def test_drifted_when_remote_no_local(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            with patch(
                "lib.capability_detect._run_cmd",
                return_value=(0, "x", ""),
            ):
                r = detect_code_repo("x", paths)
            self.assertEqual(r["state"], "drifted")
            self.assertIn("drift_reason", r)


class TestDetectKnowledgeSlot(unittest.TestCase):
    def test_absent_when_kb_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_knowledge_slot("x", paths)
            self.assertEqual(r["state"], "absent")
            self.assertEqual(r["folders_present"], 0)

    def test_partial_when_some_folders(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            paths.kb_dir.mkdir(parents=True)
            # First call lists top-level (3 folders containing slug)
            # Subsequent calls list each folder's subdirs (slug present)
            calls = iter([
                (0, "10_prd\n40_roadmap\n30_adr", ""),
                (0, "x\nbevox-site", ""),
                (0, "x", ""),
                (0, "x", ""),
            ])
            with patch(
                "lib.capability_detect._run_cmd",
                side_effect=lambda *a, **kw: next(calls),
            ):
                r = detect_knowledge_slot("x", paths)
            self.assertEqual(r["state"], "partial")
            self.assertEqual(r["folders_present"], 3)

    def test_partial_with_drift_reason_when_git_ls_tree_fails(self):
        """W1 review fix #2: rc!=0 must surface drift_reason
        (e.g., fresh clone without origin/main fetched), not silent absent.
        """
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            paths.kb_dir.mkdir(parents=True)
            with patch(
                "lib.capability_detect._run_cmd",
                return_value=(128, "", "fatal: bad revision 'origin/main'"),
            ):
                r = detect_knowledge_slot("x", paths)
            self.assertEqual(r["state"], "partial")
            self.assertEqual(r["folders_present"], 0)
            self.assertIn("drift_reason", r)
            self.assertIn("rc=128", r["drift_reason"])
            self.assertIn("fatal: bad revision", r["drift_reason"])

    def test_provisioned_when_all_9_folders(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            paths.kb_dir.mkdir(parents=True)
            top_level = "\n".join((
                "00_inbox", "10_prd", "20_architecture", "30_adr",
                "35_specs", "40_roadmap", "50_releases",
                "60_customer-feedback", "70_metrics",
            ))
            # First call returns all 9 top-level; next 9 each return "x"
            sequence = [(0, top_level, "")] + [(0, "x", "")] * 9
            calls = iter(sequence)
            with patch(
                "lib.capability_detect._run_cmd",
                side_effect=lambda *a, **kw: next(calls),
            ):
                r = detect_knowledge_slot("x", paths)
            self.assertEqual(r["state"], "provisioned")
            self.assertEqual(r["folders_present"], 9)


class TestDetectKanbanSprints(unittest.TestCase):
    def test_absent_when_no_state_json(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_kanban_sprints("x", paths)
            self.assertEqual(r["state"], "absent")

    def test_provisioned_when_current_and_next(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            kdir = paths.openclaw_dir / "kanban-tasks"
            kdir.mkdir(parents=True)
            (kdir / "state.json").write_text(json.dumps({
                "sprints": [
                    {"id": "s1", "project": "x", "status": "current"},
                    {"id": "s2", "project": "x", "status": "next"},
                    {"id": "s3", "project": "y", "status": "current"},
                ],
            }))
            r = detect_kanban_sprints("x", paths)
            self.assertEqual(r["state"], "provisioned")
            self.assertEqual(r["current_sprint"], "s1")
            self.assertEqual(r["next_sprint"], "s2")

    def test_partial_when_only_current(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            kdir = paths.openclaw_dir / "kanban-tasks"
            kdir.mkdir(parents=True)
            (kdir / "state.json").write_text(json.dumps({
                "sprints": [
                    {"id": "s1", "project": "x", "status": "current"},
                ],
            }))
            r = detect_kanban_sprints("x", paths)
            self.assertEqual(r["state"], "partial")
            self.assertEqual(r["current_sprint"], "s1")
            self.assertIsNone(r["next_sprint"])


class TestDetectWorkspace(unittest.TestCase):
    def test_absent_when_dir_missing(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_workspace("x", paths)
            self.assertEqual(r["state"], "absent")

    def test_partial_when_no_identity(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            (paths.openclaw_dir / "workspace-x").mkdir(parents=True)
            r = detect_workspace("x", paths)
            self.assertEqual(r["state"], "partial")
            self.assertIn("drift_reason", r)

    def test_provisioned_when_full(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            ws = paths.openclaw_dir / "workspace-x"
            ws.mkdir(parents=True)
            (ws / "IDENTITY.md").write_text("---\nfoo: bar\n---\n")
            r = detect_workspace("x", paths)
            self.assertEqual(r["state"], "provisioned")


class TestDetectPersona(unittest.TestCase):
    def test_absent_when_no_identity(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_persona("x", paths)
            self.assertEqual(r["state"], "absent")

    def test_partial_when_pending(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            ws = paths.openclaw_dir / "workspace-x"
            ws.mkdir(parents=True)
            (ws / "IDENTITY.md").write_text(
                "---\npersona_status: pending\n---\n"
            )
            r = detect_persona("x", paths)
            self.assertEqual(r["state"], "partial")
            self.assertEqual(r["persona_status"], "pending")

    def test_provisioned_when_generated(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            ws = paths.openclaw_dir / "workspace-x"
            ws.mkdir(parents=True)
            (ws / "IDENTITY.md").write_text(
                "---\npersona_status: generated\n---\n"
            )
            r = detect_persona("x", paths)
            self.assertEqual(r["state"], "provisioned")


class TestDetectBot(unittest.TestCase):
    def test_absent_when_no_meta_entry(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_bot("x", paths, None)
            self.assertEqual(r["state"], "absent")

    def test_absent_when_bot_id_null(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_bot("x", paths, {"bot_id": None})
            self.assertEqual(r["state"], "absent")

    def test_drifted_when_bot_id_but_nothing_else(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            with patch.dict("os.environ", {"HOME": td}):
                r = detect_bot(
                    "x", paths,
                    {"bot_id": "my-bot", "bot_port": 8042},
                    skip_systemctl=True,
                )
            self.assertEqual(r["state"], "drifted")

    def test_provisioned_when_profile_and_systemd(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            (Path(td) / ".openclaw-my-bot").mkdir()
            with patch.dict("os.environ", {"HOME": td}):
                r = detect_bot(
                    "x", paths,
                    {"bot_id": "my-bot", "bot_port": 8042},
                    skip_systemctl=True,  # treats profile-present as systemd-active
                )
            self.assertEqual(r["state"], "provisioned")
            self.assertEqual(r["area"], "my-bot")
            self.assertEqual(r["port"], 8042)


class TestDetectTelegramTopics(unittest.TestCase):
    def test_absent_when_no_meta(self):
        r = detect_telegram_topics("x", _make_paths("/tmp"), None)
        self.assertEqual(r["state"], "absent")

    def test_absent_when_no_topics_field(self):
        r = detect_telegram_topics(
            "x", _make_paths("/tmp"), {"telegram": {}},
        )
        self.assertEqual(r["state"], "absent")

    def test_partial_when_only_some_threads(self):
        r = detect_telegram_topics(
            "x", _make_paths("/tmp"),
            {"telegram": {"topics": {
                "clarifications": 17, "dispatcher": None, "blocks": None, "knowledge": None,
            }}},
        )
        self.assertEqual(r["state"], "partial")
        self.assertEqual(r["clarifications"], 17)

    def test_provisioned_when_all_four(self):
        r = detect_telegram_topics(
            "x", _make_paths("/tmp"),
            {"telegram": {"topics": {
                "clarifications": 17, "dispatcher": 18, "blocks": 19, "knowledge": 20,
            }}},
        )
        self.assertEqual(r["state"], "provisioned")


class TestDetectMissionControl(unittest.TestCase):
    def test_always_absent_in_w1(self):
        r = detect_mission_control("x", _make_paths("/tmp"), {})
        self.assertEqual(r["state"], "absent")


class TestDetectAll(unittest.TestCase):
    def test_returns_all_8_capabilities(self):
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_all(
                "x", paths, meta_entry={},
                skip_remote=True, skip_systemctl=True,
            )
            self.assertEqual(set(r.keys()), {
                "code_repo", "knowledge_slot", "kanban_sprints", "workspace",
                "persona", "bot", "telegram_topics", "mission_control",
            })
            for cap in r.values():
                self.assertIn("state", cap)

    def test_skip_knowledge_returns_skipped_state(self):
        """W1 review fix #2: skip_knowledge=True bypasses detect_knowledge_slot."""
        with tempfile.TemporaryDirectory() as td:
            paths = _make_paths(td)
            r = detect_all(
                "x", paths, meta_entry={},
                skip_remote=True, skip_systemctl=True,
                skip_knowledge=True,
            )
            self.assertEqual(r["knowledge_slot"]["state"], "skipped")
            self.assertIn("drift_reason", r["knowledge_slot"])


if __name__ == "__main__":
    unittest.main()
