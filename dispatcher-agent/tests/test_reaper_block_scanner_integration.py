"""Integration test: reaper tick invoca block_scanner + escalation_dispatcher."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from lib import reaper


class TestReaperBlockScannerStage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_kill_switch_skips_block_scanner(self):
        """Env OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER=1 → stage no-op."""
        with patch.dict(os.environ, {"OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER": "1"}):
            with patch.object(reaper, "_block_scanner_module") as mock_scanner:
                stats = reaper._block_scanner_stage({})
                mock_scanner.scan_all.assert_not_called()
        self.assertTrue(stats["skipped_kill_switch"])

    def test_normal_flow_calls_scan_and_dispatch(self):
        """Sem kill switch → chama scan_all + dispatch pra cada candidate."""
        from lib.block_scanner import Candidate
        candidate = Candidate(
            task_id="T-0070", criterion="blocked",
            block_session_key="k", block_reason="x", project="p")
        env_clean = {k: v for k, v in os.environ.items()
                     if k != "OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER"}
        with patch.dict(os.environ, env_clean, clear=True):
            with patch.object(reaper, "_block_scanner_module") as mock_scanner:
                with patch.object(reaper, "_escalation_dispatcher_module") as mock_dispatcher:
                    mock_scanner.scan_all.return_value = [candidate]
                    mock_scanner.next_escalation_seq.return_value = 1
                    mock_dispatcher.render_escalation_file.return_value = Path("/tmp/T-0070-blk-1.md")
                    mock_dispatcher.dispatch_telegram.return_value = {"sent": True, "message_id": 100}
                    stats = reaper._block_scanner_stage({"tasks": []})
                    mock_scanner.scan_all.assert_called_once()
                    mock_dispatcher.render_escalation_file.assert_called_once()
                    mock_dispatcher.dispatch_telegram.assert_called_once()
        self.assertEqual(stats["candidates_found"], 1)
        self.assertEqual(stats["escalations_created"], 1)
        self.assertEqual(stats["telegram_sent"], 1)
        self.assertFalse(stats["skipped_kill_switch"])

    def test_exception_in_block_scanner_does_not_propagate(self):
        """Try/except local — falha do block_scanner não derruba reaper."""
        env_clean = {k: v for k, v in os.environ.items()
                     if k != "OPENCLAW_REAPER_DISABLE_BLOCK_SCANNER"}
        with patch.dict(os.environ, env_clean, clear=True):
            with patch.object(reaper, "_block_scanner_module") as mock_scanner:
                mock_scanner.scan_all.side_effect = RuntimeError("boom")
                try:
                    stats = reaper._block_scanner_stage({"tasks": []})
                except RuntimeError:
                    self.fail("Block scanner exception escaped — should be caught locally")
        self.assertGreaterEqual(stats["errors"], 1)


if __name__ == "__main__":
    unittest.main()
