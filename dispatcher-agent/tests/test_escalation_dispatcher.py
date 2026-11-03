"""Unit tests for UBN escalation_dispatcher.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-30-universal-block-notifier.md §4-§5
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from lib import escalation_dispatcher
from lib.block_scanner import Candidate


class TestRenderEscalationFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_renders_with_full_frontmatter(self):
        candidate = Candidate(
            task_id="T-0050", criterion="blocked",
            block_session_key="2026-04-30T15:00:00Z",
            block_reason="test_failed: AC1 something",
            project="bevox-site",
        )
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(candidate, seq=1)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("escalation_id: T-0050-blk-1", content)
        self.assertIn("task_id: T-0050", content)
        self.assertIn("project: bevox-site", content)
        self.assertIn("criterion: blocked", content)
        self.assertIn("block_session_key: 2026-04-30T15:00:00Z", content)
        self.assertIn("status: open", content)
        self.assertIn("dispatched_at: null", content)

    def test_filename_format(self):
        candidate = Candidate(
            task_id="T-0051", criterion="blocked",
            block_session_key="x", block_reason="y", project="p",
        )
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(candidate, seq=3)
        self.assertEqual(path.name, "T-0051-blk-3.md")

    def test_renders_none_block_session_key_as_none_literal(self):
        """Candidate com block_session_key=None vira '(none)' no frontmatter
        — alinhado com find_open_escalation dedup convention."""
        candidate = Candidate(
            task_id="T-0052", criterion="blocked",
            block_session_key=None,
            block_reason="x", project="p",
        )
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(candidate, seq=1)
        content = path.read_text()
        self.assertIn("block_session_key: (none)", content)


class TestSendTelegram(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.candidate = Candidate(
            task_id="T-0060", criterion="blocked",
            block_session_key="2026-04-30T16:00:00Z",
            block_reason="test_failed: AC X",
            project="bevox-site",
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _full_env(self):
        return {
            "TELEGRAM_BOT_TOKEN": "tok-abc",
            "OPENCLAW_BLOCKS_TELEGRAM_CHAT_ID": "-1001234567890",
            "OPENCLAW_BLOCKS_TELEGRAM_THREAD_ID": "99",
        }

    def test_dispatch_falls_back_to_global_env_when_no_per_project(self):
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(self.candidate, seq=1)
            with patch.dict(os.environ, self._full_env(), clear=True):
                # Patch resolve_telegram_target to return None (no per-project mapping)
                import sys as _sys
                tm_module = _sys.modules.get("telegram_meta")
                if tm_module is not None:
                    with patch.object(tm_module, "resolve_telegram_target", return_value=None):
                        with patch.object(escalation_dispatcher._notifier, "_send_http",
                                          return_value=(True, {"message_id": 777})):
                            result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
                else:
                    with patch.object(escalation_dispatcher._notifier, "_send_http",
                                      return_value=(True, {"message_id": 777})):
                        result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
        self.assertTrue(result["sent"])
        content = path.read_text()
        self.assertIn("telegram_message_id: 777", content)
        self.assertNotIn("dispatched_at: null", content)

    def test_dispatch_marks_failure_when_telegram_down(self):
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(self.candidate, seq=1)
            with patch.dict(os.environ, self._full_env(), clear=True):
                import sys as _sys
                tm_module = _sys.modules.get("telegram_meta")
                if tm_module is not None:
                    with patch.object(tm_module, "resolve_telegram_target", return_value=None):
                        with patch.object(escalation_dispatcher._notifier, "_send_http",
                                          return_value=(False, {"error": "telegram_api_500"})):
                            result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
                else:
                    with patch.object(escalation_dispatcher._notifier, "_send_http",
                                      return_value=(False, {"error": "telegram_api_500"})):
                        result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
        self.assertFalse(result["sent"])
        content = path.read_text()
        self.assertIn("dispatched_at: null", content)
        self.assertIn("telegram_message_id: null", content)

    def test_dispatch_returns_no_target_when_env_missing(self):
        """Sem env vars + sem per-project → result.sent=False, reason='no_telegram_target'."""
        with patch.object(escalation_dispatcher, "UBN_ESCALATIONS_DIR", Path(self.tmp)):
            path = escalation_dispatcher.render_escalation_file(self.candidate, seq=1)
            with patch.dict(os.environ, {}, clear=True):
                import sys as _sys
                tm_module = _sys.modules.get("telegram_meta")
                if tm_module is not None:
                    with patch.object(tm_module, "resolve_telegram_target", return_value=None):
                        result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
                else:
                    result = escalation_dispatcher.dispatch_telegram(path, self.candidate)
        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "no_telegram_target")


class TestResolveTargetKindRouting(unittest.TestCase):
    """kind-aware routing in _resolve_target (W0 step 8)."""

    def test_block_kind_uses_blocks_envs(self):
        """Default kind='block' resolves to OPENCLAW_BLOCKS_TELEGRAM_* env vars."""
        env = {
            "TELEGRAM_BOT_TOKEN": "fake-token",
            "OPENCLAW_BLOCKS_TELEGRAM_CHAT_ID": "-100123",
            "OPENCLAW_BLOCKS_TELEGRAM_THREAD_ID": "10",
        }
        with patch.dict(os.environ, env, clear=True):
            result = escalation_dispatcher._resolve_target(None, kind="block")
        self.assertEqual(result, ("fake-token", "-100123", 10, "global"))

    def test_doc_gap_uses_knowledge_envs(self):
        """kind='doc-gap' resolves to OPENCLAW_KNOWLEDGE_TELEGRAM_* env vars."""
        env = {
            "TELEGRAM_BOT_TOKEN": "fake-token",
            "OPENCLAW_KNOWLEDGE_TELEGRAM_CHAT_ID": "-100456",
            "OPENCLAW_KNOWLEDGE_TELEGRAM_THREAD_ID": "42",
        }
        with patch.dict(os.environ, env, clear=True):
            result = escalation_dispatcher._resolve_target(None, kind="doc-gap")
        self.assertEqual(result, ("fake-token", "-100456", 42, "global"))

    def test_doc_bootstrap_routes_to_knowledge(self):
        """kind='doc-bootstrap' shares 'knowledge' topic with doc-gap."""
        env = {
            "TELEGRAM_BOT_TOKEN": "fake-token",
            "OPENCLAW_KNOWLEDGE_TELEGRAM_CHAT_ID": "-100789",
            "OPENCLAW_KNOWLEDGE_TELEGRAM_THREAD_ID": "99",
        }
        with patch.dict(os.environ, env, clear=True):
            result = escalation_dispatcher._resolve_target(None, kind="doc-bootstrap")
        self.assertEqual(result, ("fake-token", "-100789", 99, "global"))

    def test_default_kind_is_block(self):
        """No kind passed defaults to 'block' (backward-compat)."""
        env = {
            "TELEGRAM_BOT_TOKEN": "fake-token",
            "OPENCLAW_BLOCKS_TELEGRAM_CHAT_ID": "-100111",
            "OPENCLAW_BLOCKS_TELEGRAM_THREAD_ID": "5",
        }
        with patch.dict(os.environ, env, clear=True):
            result = escalation_dispatcher._resolve_target(None)  # no kind arg
        self.assertEqual(result, ("fake-token", "-100111", 5, "global"))

    def test_unknown_kind_falls_back_to_blocks(self):
        """Unknown kind falls back to 'blocks' topic + envs (defensive default)."""
        env = {
            "TELEGRAM_BOT_TOKEN": "fake-token",
            "OPENCLAW_BLOCKS_TELEGRAM_CHAT_ID": "-100222",
            "OPENCLAW_BLOCKS_TELEGRAM_THREAD_ID": "7",
        }
        with patch.dict(os.environ, env, clear=True):
            result = escalation_dispatcher._resolve_target(None, kind="invalid-kind")
        self.assertEqual(result, ("fake-token", "-100222", 7, "global"))


class TestResolveTargetBotKnowledgeRouting(unittest.TestCase):
    """W3.5: kind ∈ {doc-gap, doc-bootstrap, retirement-flag} routes to bot-knowledge group."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_meta(self, data: dict) -> str:
        p = Path(self.tmp) / "projects-meta.json"
        p.write_text(json.dumps(data))
        return str(p)

    def test_resolve_target_doc_gap_routes_to_bot_knowledge(self):
        """W3.5: kind=doc-gap routes to bot-knowledge group via projects-meta.bot_knowledge."""
        meta = {
            "projects": [{"id": "bevox-direct"}],
            "bot_knowledge": {
                "chat_id": "-1003999",
                "bot_id": "voz-knowledge",
                "topics": {"bevox-direct": 7},
            },
        }
        meta_path = self._write_meta(meta)
        env = {
            "OPENCLAW_PROJECTS_META": meta_path,
            "BOT_TOKEN_VOZ_KNOWLEDGE": "tok-test",
        }
        with patch.dict(os.environ, env, clear=True):
            target = escalation_dispatcher._resolve_target("bevox-direct", kind="doc-gap")
        self.assertIsNotNone(target)
        token, chat_id, thread_id, alias = target
        self.assertEqual(token, "tok-test")
        self.assertEqual(str(chat_id), "-1003999")
        self.assertEqual(thread_id, 7)

    def test_resolve_target_legacy_flag_keeps_per_project_routing(self):
        """OPENCLAW_KNOWLEDGE_DISPATCH_LEGACY=true → keep legacy env routing."""
        env = {
            "OPENCLAW_KNOWLEDGE_DISPATCH_LEGACY": "true",
            "TELEGRAM_BOT_TOKEN": "legacy-tok",
            "OPENCLAW_KNOWLEDGE_TELEGRAM_CHAT_ID": "-1009999",
            "OPENCLAW_KNOWLEDGE_TELEGRAM_THREAD_ID": "5",
        }
        with patch.dict(os.environ, env, clear=True):
            target = escalation_dispatcher._resolve_target(None, kind="doc-gap")
        self.assertIsNotNone(target)
        token, chat_id, thread_id, alias = target
        self.assertEqual(token, "legacy-tok")
        self.assertEqual(thread_id, 5)
        self.assertEqual(alias, "global")

    def test_resolve_target_no_bot_knowledge_config_returns_none(self):
        """Sem bot_knowledge config E sem legacy flag → returns None (W3.5 fail-fast)."""
        meta = {"projects": [{"id": "bevox-direct"}]}  # No bot_knowledge section
        meta_path = self._write_meta(meta)
        env = {"OPENCLAW_PROJECTS_META": meta_path}
        with patch.dict(os.environ, env, clear=True):
            target = escalation_dispatcher._resolve_target("bevox-direct", kind="doc-gap")
        self.assertIsNone(target)

    def test_resolve_target_block_kind_unchanged(self):
        """kind=block (UBN) NUNCA é afetado pela migração — mantém legacy resolver."""
        env = {
            "TELEGRAM_BOT_TOKEN": "block-tok",
            "OPENCLAW_BLOCKS_TELEGRAM_CHAT_ID": "-1001234",
            "OPENCLAW_BLOCKS_TELEGRAM_THREAD_ID": "1",
        }
        with patch.dict(os.environ, env, clear=True):
            target = escalation_dispatcher._resolve_target(None, kind="block")
        self.assertIsNotNone(target)
        token, chat_id, thread_id, alias = target
        self.assertEqual(token, "block-tok")

    def test_resolve_target_retirement_flag_routes_to_bot_knowledge(self):
        """W3.5: kind=retirement-flag (F4) também rota para bot-knowledge."""
        meta = {
            "projects": [{"id": "openclaw"}],
            "bot_knowledge": {
                "chat_id": "-1003888",
                "bot_id": "voz-knowledge",
                "topics": {"openclaw": 11},
            },
        }
        meta_path = self._write_meta(meta)
        env = {
            "OPENCLAW_PROJECTS_META": meta_path,
            "BOT_TOKEN_VOZ_KNOWLEDGE": "tok-test",
        }
        with patch.dict(os.environ, env, clear=True):
            target = escalation_dispatcher._resolve_target("openclaw", kind="retirement-flag")
        self.assertIsNotNone(target)
        token, chat_id, thread_id, alias = target
        self.assertEqual(thread_id, 11)

    def test_resolve_target_doc_bootstrap_routes_to_bot_knowledge(self):
        """W3.5: kind=doc-bootstrap também rota para bot-knowledge."""
        meta = {
            "projects": [{"id": "openclaw"}],
            "bot_knowledge": {
                "chat_id": "-1003777",
                "bot_id": "voz-knowledge",
                "topics": {"openclaw": 3},
            },
        }
        meta_path = self._write_meta(meta)
        env = {
            "OPENCLAW_PROJECTS_META": meta_path,
            "BOT_TOKEN_VOZ_KNOWLEDGE": "tok-bootstrap",
        }
        with patch.dict(os.environ, env, clear=True):
            target = escalation_dispatcher._resolve_target("openclaw", kind="doc-bootstrap")
        self.assertIsNotNone(target)
        token, chat_id, thread_id, alias = target
        self.assertEqual(token, "tok-bootstrap")
        self.assertEqual(thread_id, 3)


if __name__ == "__main__":
    unittest.main()
