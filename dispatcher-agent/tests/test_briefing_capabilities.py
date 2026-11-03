"""Tests for capabilities block rendering in briefing.

Spec: bevox-knowledge/35_specs/openclaw/2026-04-29-dispatcher-notifier-tester-decision-and-capability-gating.md §5
"""
import unittest

from lib import briefing


class TestCapabilitiesBlock(unittest.TestCase):
    def _task(self, requires_capability=None):
        payload = {
            "goal": "do thing",
            "acceptance_criteria": ["AC1"],
        }
        if requires_capability is not None:
            payload["requires_capability"] = requires_capability
        return {
            "id": "T-0001",
            "title": "Sample",
            "epic_id": "E1",
            "wave_ref": "w1",
            "dispatch_payload": payload,
        }

    def test_no_capabilities_no_block(self):
        rendered = briefing.render_briefing(self._task(), "Read,Write")
        self.assertNotIn("Capabilities requeridas", rendered)
        self.assertNotIn("CAPABILITY_MISSING", rendered)

    def test_capabilities_renders_block_and_protocol(self):
        rendered = briefing.render_briefing(
            self._task(requires_capability=["docker_build"]),
            "Read,Write,Bash(docker build:*)",
        )
        self.assertIn("Capabilities requeridas", rendered)
        self.assertIn("docker_build", rendered)
        self.assertIn("CAPABILITY_MISSING:", rendered)
        self.assertIn("inconclusive", rendered)

    def test_multiple_capabilities_listed(self):
        rendered = briefing.render_briefing(
            self._task(requires_capability=["docker_build", "internet_egress"]),
            "Read",
        )
        self.assertIn("`docker_build`", rendered)
        self.assertIn("`internet_egress`", rendered)


if __name__ == "__main__":
    unittest.main()
