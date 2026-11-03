"""Tests for claude_project_dir + load_session_evidence + load_evidence."""
import unittest
from pathlib import Path

# Claude Code encodes a project dir by replacing "/" with "-".
_HOME_ENC = str(Path.home()).replace("/", "-")

from lib import context_loader


class TestClaudeProjectDir(unittest.TestCase):
    def test_simple_path(self):
        self.assertEqual(
            context_loader.claude_project_dir(f"{Path.home()}/code/bevox-site"),
            _HOME_ENC + "-code-bevox-site",
        )

    def test_home_path(self):
        self.assertEqual(
            context_loader.claude_project_dir(f"{Path.home()}"),
            _HOME_ENC,
        )

    def test_tilde_expansion(self):
        # ~ expande para $HOME
        result = context_loader.claude_project_dir("~/code/bevox-site")
        self.assertEqual(result, _HOME_ENC + "-code-bevox-site")

    def test_trailing_slash_stripped(self):
        self.assertEqual(
            context_loader.claude_project_dir(f"{Path.home()}/code/bevox-site/"),
            _HOME_ENC + "-code-bevox-site",
        )

    def test_root_path(self):
        self.assertEqual(context_loader.claude_project_dir("/"), "-")


import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TestLoadSessionEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Mock structure: ~/.claude/projects/<encoded-project-dir>/<sess>.jsonl
        self.proj_dir = self.tmp / "projects" / (_HOME_ENC + "-code-bevox-site")
        self.proj_dir.mkdir(parents=True)
        self.session_id = "abc1234-def5-6789-aaaa-bbbbccccdddd"
        self.session_path = self.proj_dir / f"{self.session_id}.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_session(self, lines):
        with open(self.session_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

    def test_returns_none_when_jsonl_missing(self):
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                "nonexistent-session", f"{Path.home()}/code/bevox-site",
            )
        self.assertIsNone(result)

    def test_parses_valid_jsonl_with_assistant_text(self):
        self._write_session([
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {"type": "assistant", "timestamp": "2026-04-29T10:00:00Z",
             "message": {"role": "assistant", "model": "claude-opus-4-7",
                         "content": [{"type": "text", "text": "Done"}]}},
        ])
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, f"{Path.home()}/code/bevox-site",
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["session_id"], self.session_id)
        self.assertEqual(result["final_assistant_text"], "Done")
        self.assertEqual(result["model"], "claude-opus-4-7")
        self.assertEqual(result["raw_lines_count"], 2)
        self.assertEqual(result["source"], "jsonl")

    def test_extracts_tool_uses_and_files_touched(self):
        self._write_session([
            {"type": "assistant", "timestamp": "2026-04-29T10:00:00Z",
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "name": "Write",
                  "input": {"file_path": "/tmp/foo.txt", "content": "x"}},
                 {"type": "tool_use", "name": "Edit",
                  "input": {"file_path": "/tmp/bar.py", "old_string": "a", "new_string": "b"}},
                 {"type": "tool_use", "name": "Read",
                  "input": {"file_path": "/tmp/baz.md"}},
             ]}},
        ])
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, f"{Path.home()}/code/bevox-site",
            )
        self.assertEqual(len(result["tool_uses"]), 3)
        # files_touched: só Write/Edit (não Read)
        self.assertIn("/tmp/foo.txt", result["files_touched"])
        self.assertIn("/tmp/bar.py", result["files_touched"])
        self.assertNotIn("/tmp/baz.md", result["files_touched"])

    def test_handles_corrupt_lines_gracefully(self):
        # write some valid lines + one corrupt
        with open(self.session_path, "w") as f:
            f.write(json.dumps({"type": "user",
                                "message": {"role": "user", "content": "hi"}}) + "\n")
            f.write("CORRUPTED LINE NOT JSON\n")
            f.write(json.dumps({"type": "assistant",
                                "timestamp": "2026-04-29T10:00:00Z",
                                "message": {"role": "assistant",
                                            "content": [{"type": "text", "text": "ok"}]}}) + "\n")
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, f"{Path.home()}/code/bevox-site",
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["final_assistant_text"], "ok")
        self.assertEqual(result["raw_lines_count"], 3)

    def test_returns_none_when_only_corrupt(self):
        with open(self.session_path, "w") as f:
            f.write("not json\n")
            f.write("also not json\n")
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, f"{Path.home()}/code/bevox-site",
            )
        self.assertIsNone(result)

    def test_empty_final_text_when_only_user_messages(self):
        self._write_session([
            {"type": "user", "message": {"role": "user", "content": "hi"}},
            {"type": "user", "message": {"role": "user", "content": "ping"}},
        ])
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, f"{Path.home()}/code/bevox-site",
            )
        self.assertIsNotNone(result)
        self.assertEqual(result["final_assistant_text"], "")

    def test_notebook_edit_uses_notebook_path(self):
        self._write_session([
            {"type": "assistant", "timestamp": "2026-04-29T10:00:00Z",
             "message": {"role": "assistant", "content": [
                 {"type": "tool_use", "name": "NotebookEdit",
                  "input": {"notebook_path": "/tmp/qux.ipynb",
                            "new_source": "print('hi')"}},
             ]}},
        ])
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            result = context_loader.load_session_evidence(
                self.session_id, f"{Path.home()}/code/bevox-site",
            )
        self.assertIn("/tmp/qux.ipynb", result["files_touched"])


class TestLoadEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.proj_dir = self.tmp / "projects" / (_HOME_ENC + "-code-bevox-site")
        self.proj_dir.mkdir(parents=True)
        self.session_id = "sess-uuid-1234"
        self.session_path = self.proj_dir / f"{self.session_id}.jsonl"
        # Also mock execution.log dir
        self.exec_dir = self.tmp / "executions"
        self.exec_dir.mkdir(parents=True)
        self.exec_log = self.exec_dir / "T-9999.log"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_uses_jsonl_when_available(self):
        with open(self.session_path, "w") as f:
            f.write(json.dumps({"type": "assistant",
                                "timestamp": "2026-04-29T10:00:00Z",
                                "message": {"role": "assistant",
                                            "content": [{"type": "text", "text": "ok"}]}}) + "\n")
        # exec log also exists with content (should be IGNORED because jsonl wins)
        self.exec_log.write_text("execution log content (should not be used)")

        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            with patch.object(context_loader, "execution_log_path",
                              return_value=self.exec_log):
                result = context_loader.load_evidence(
                    "T-9999", self.session_id, f"{Path.home()}/code/bevox-site",
                )
        self.assertEqual(result["evidence_source"], "jsonl")
        self.assertEqual(result["final_assistant_text"], "ok")

    def test_falls_back_to_execution_log_when_jsonl_missing(self):
        # No jsonl created. Exec log has content.
        self.exec_log.write_text("real execution log content here")

        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            with patch.object(context_loader, "execution_log_path",
                              return_value=self.exec_log):
                result = context_loader.load_evidence(
                    "T-9999", self.session_id, f"{Path.home()}/code/bevox-site",
                )
        self.assertEqual(result["evidence_source"], "execution_log_fallback")
        self.assertIn("real execution log content", result["execution_log_tail"])

    def test_falls_back_when_session_id_none(self):
        self.exec_log.write_text("fallback content")
        with patch.object(context_loader, "execution_log_path",
                          return_value=self.exec_log):
            result = context_loader.load_evidence("T-9999", None, None)
        self.assertEqual(result["evidence_source"], "execution_log_fallback")

    def test_both_empty_returns_empty_evidence_with_fallback_marker(self):
        # No jsonl, exec log empty
        with patch.object(context_loader, "_claude_projects_root",
                          return_value=self.tmp / "projects"):
            with patch.object(context_loader, "execution_log_path",
                              return_value=self.exec_log):  # exec_log doesn't exist
                result = context_loader.load_evidence("T-9999", "missing", None)
        self.assertEqual(result["evidence_source"], "execution_log_fallback")
        self.assertEqual(result["execution_log_tail"], "")


class TestBuildTestContextEvidence(unittest.TestCase):
    """Verifies build_test_context uses load_evidence (jsonl primary)."""

    def test_carries_evidence_source_field(self):
        """When task has session_id and project, load_evidence is consulted."""
        from unittest.mock import patch, MagicMock
        fake_task = {
            "id": "T-9999",
            "project": "bevox-site",
            "dispatch_payload": {
                "execution_session_id": "fake-sess-uuid",
                "acceptance_criteria": ["AC1"],
            },
        }
        fake_evidence = {
            "task_id": "T-9999",
            "session_id": "fake-sess-uuid",
            "evidence_source": "jsonl",
            "final_assistant_text": "all done",
            "tool_uses": [],
            "tool_results": [],
            "files_touched": [],
        }
        with patch.object(context_loader, "load_task_via_kanban",
                          return_value=fake_task):
            with patch.object(context_loader, "load_evidence",
                              return_value=fake_evidence) as mock_load:
                ctx = context_loader.build_test_context("T-9999")
        self.assertIn("evidence_source", ctx)
        self.assertEqual(ctx["evidence_source"], "jsonl")
        self.assertEqual(ctx["evidence"]["final_assistant_text"], "all done")
        # Verify load_evidence was called with task + session_id
        mock_load.assert_called_once()
        args = mock_load.call_args
        self.assertEqual(args[0][0], "T-9999")
        self.assertEqual(args[0][1], "fake-sess-uuid")


if __name__ == "__main__":
    unittest.main()
