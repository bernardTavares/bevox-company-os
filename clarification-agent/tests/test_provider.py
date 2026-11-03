"""Testes provider.run — local-first abstraction."""
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from lib import drafter as drafter_lib
from lib import provider


class TestProviderRun(unittest.TestCase):
    def test_ollama_success_returns_parsed(self):
        raw_json = '{"answer":"ok","sources":["/x"],"confidence":"safe","escalation_reason":""}'
        with patch("lib.provider._run_ollama") as mock:
            mock.return_value = (raw_json, 1234)
            out = provider.run(prompt="p", model="qwen2.5-coder:14b",
                               timeout=30, provider="ollama")
        self.assertEqual(out["provider_used"], "ollama")
        self.assertEqual(out["parsed"]["confidence"], "safe")
        self.assertEqual(out["latency_ms"], 1234)
        self.assertIsNone(out["error"])

    def test_claude_cli_success_returns_parsed(self):
        raw_json = '```json\n{"answer":"ok","sources":["/x"],"confidence":"unsafe","escalation_reason":"r"}\n```'
        with patch("lib.provider._run_claude_cli") as mock:
            mock.return_value = (raw_json, 2345)
            out = provider.run(prompt="p", model="claude-haiku-4-5",
                               timeout=20, provider="claude_cli")
        self.assertEqual(out["provider_used"], "claude_cli")
        self.assertEqual(out["parsed"]["confidence"], "unsafe")

    def test_timeout_returns_error(self):
        with patch("lib.provider._run_ollama") as mock:
            mock.side_effect = TimeoutError("30s hit")
            out = provider.run(prompt="p", model="qwen2.5-coder:14b",
                               timeout=30, provider="ollama")
        self.assertEqual(out["error"], "timeout")
        self.assertIsNone(out["parsed"])


class TestDrafterLocalFirst(unittest.TestCase):
    """draft_answer com provider local já cobre o caso happy local.
    A escolha local→cloud é orquestrada por draft_answer_local_first
    (criado na task 6). Este test valida apenas o provider switch."""

    def _ctx(self):
        return {
            "task": {"title": "x", "epic_id": "E10", "wave_ref": "w"},
            "dispatch_payload": {"goal": "g", "acceptance_criteria": ["a"],
                                 "files_relevant": [], "guardrails": [],
                                 "out_of_scope": []},
            "read_refs": [{"ref": "s", "path": f"{Path.home()}/bevox-knowledge/README.md",
                           "content": "stub"}],
            "unresolved_refs": [],
        }

    def test_provider_param_is_respected(self):
        """Provider local invocado quando passado explicit."""
        raw_json = f'{{"answer":"ok","sources":["{Path.home()}/bevox-knowledge/README.md"],"confidence":"safe","escalation_reason":""}}'
        with patch("lib.provider._run_ollama") as mo, \
             patch("lib.safety.validate_sources") as ms:
            mo.return_value = (raw_json, 1000)
            ms.return_value = ([f"{Path.home()}/bevox-knowledge/README.md"], [])
            out = drafter_lib.draft_answer(
                "T-1", "q?", ctx_bundle=self._ctx(),
                model="qwen2.5-coder:14b", provider="ollama", timeout=15,
            )
        self.assertEqual(out["drafter_provider"], "ollama")
        self.assertEqual(out["confidence"], "safe")


class TestLocalFirstChain(unittest.TestCase):
    def _ctx(self):
        return {"task":{},"dispatch_payload":{"goal":"g","acceptance_criteria":["a"],"files_relevant":[],"guardrails":[],"out_of_scope":[]},"read_refs":[],"unresolved_refs":[]}

    def test_local_safe_skips_cloud(self):
        raw = f'{{"answer":"ok","sources":["{Path.home()}/bevox-knowledge/README.md"],"confidence":"safe","escalation_reason":""}}'
        with patch("lib.provider._run_ollama") as mo, \
             patch("lib.provider._run_claude_cli") as mc, \
             patch("lib.safety.validate_sources") as ms:
            mo.return_value = (raw, 1000)
            ms.return_value = ([f"{Path.home()}/bevox-knowledge/README.md"], [])
            out = drafter_lib.draft_answer_local_first("T-1", "q?", ctx_bundle=self._ctx())
        self.assertFalse(out["local_first_fallback_used"])
        self.assertEqual(out["confidence"], "safe")
        mc.assert_not_called()

    def test_local_unsafe_triggers_cloud(self):
        raw_local = '{"answer":"maybe","sources":[],"confidence":"unsafe","escalation_reason":"ambig"}'
        raw_cloud = f'{{"answer":"ok-cloud","sources":["{Path.home()}/bevox-knowledge/README.md"],"confidence":"safe","escalation_reason":""}}'
        with patch("lib.provider._run_ollama") as mo, \
             patch("lib.provider._run_claude_cli") as mc, \
             patch("lib.safety.validate_sources") as ms:
            mo.return_value = (raw_local, 1100)
            mc.return_value = (raw_cloud, 2100)
            ms.return_value = ([f"{Path.home()}/bevox-knowledge/README.md"], [])
            out = drafter_lib.draft_answer_local_first("T-1", "q?", ctx_bundle=self._ctx())
        self.assertTrue(out["local_first_fallback_used"])
        self.assertEqual(out["confidence"], "safe")
        self.assertEqual(out["drafter_provider"], "claude_cli")
        self.assertEqual(out["local_first_local_confidence"], "unsafe")


if __name__ == "__main__":
    unittest.main()
