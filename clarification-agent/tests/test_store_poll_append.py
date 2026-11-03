"""Test store.append_poll_event."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lib import store


class TestAppendPollEvent(unittest.TestCase):
    def test_append_one_line_per_call(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_root = Path(d)
            tmp_jsonl = tmp_root / "poll.jsonl"
            with patch.object(store, "POLL_JSONL", tmp_jsonl), \
                 patch.object(store, "ROOT", tmp_root):
                store.append_poll_event("tick-1", "ev_a", {"k": 1})
                store.append_poll_event("tick-1", "ev_b", {"k": 2})
            lines = tmp_jsonl.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)
        e0 = json.loads(lines[0])
        self.assertEqual(e0["tick_id"], "tick-1")
        self.assertEqual(e0["event"], "ev_a")
        self.assertEqual(e0["payload"]["k"], 1)


if __name__ == "__main__":
    unittest.main()
