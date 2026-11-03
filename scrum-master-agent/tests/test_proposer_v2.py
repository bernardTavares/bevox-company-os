"""Testes proposer v2 (wave-6): integração com resolver + gate_check + shape."""
import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path


PLAN_HAPPY = """# Plan Happy

**Goal:** Test wave-6 scrum-master proposer.

**Epico:** E10/wave-6-scrum-master-v2

**Project:** openclaw

**Specs:** `bevox-knowledge/35_specs/xxx.md`

## Phase 1: Setup

### Task 1.1: Primeiro step

**Files:**
- Create: `a.py`

- [ ] **Step 1: Foo**

Expected: bar baz

### Task 1.2: Segundo step

**Files:**
- Create: `b.py`

- [ ] **Step 1: Foo**

Expected: bar

## Phase 2: Implementation

### Task 2.1: Componente A

**Files:**
- Create: `c.py`

- [ ] **Step 1: Impl**

Expected: all tests pass

### Task 2.2: Componente B

**Files:**
- Create: `d.py`

**Depends:** Task 1.1, Task 2.1

- [ ] **Step 1: Final**

Expected: suite green
"""

PLAN_MISSING_AC = """# Plan Missing AC

**Goal:** Plan sem Expected lines.

**Epico:** E10/wave-6-scrum-master-v2

**Project:** openclaw

## Phase 1: Setup

### Task 1.1: Sem expected

**Files:**
- Create: `a.py`

- [ ] **Step 1: Foo**
"""


def _reload_proposer():
    from lib import parser, proposer, dependency_resolver, gate_check
    importlib.reload(parser)
    importlib.reload(dependency_resolver)
    importlib.reload(gate_check)
    importlib.reload(proposer)
    return proposer


class TestBuildProposalHybrid(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scrum-v2-happy-"))
        self.plan = self.tmp / "plan.md"
        self.plan.write_text(PLAN_HAPPY)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_hybrid_mode_phase_sequence_with_override(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="hybrid",
        )
        self.assertEqual(proposal["dependency_mode"], "hybrid")
        self.assertIn("computed_deps", proposal)
        deps = proposal["computed_deps"]
        self.assertEqual(deps.get("Task 1.1", []), [])
        self.assertEqual(deps.get("Task 1.2", []), [])
        self.assertEqual(deps.get("Task 2.1", []), ["Task 1.2"])
        self.assertEqual(sorted(deps.get("Task 2.2", [])),
                         ["Task 1.1", "Task 2.1"])

    def test_proposal_task_has_label(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="hybrid",
        )
        labels = [t.get("label") for t in proposal["tasks"]]
        self.assertEqual(labels, ["Task 1.1", "Task 1.2", "Task 2.1", "Task 2.2"])

    def test_blocked_by_labels_in_dispatch_payload(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="hybrid",
        )
        by_label = {t["label"]: t for t in proposal["tasks"]}
        t22_bb = by_label["Task 2.2"]["dispatch_payload"].get("blocked_by_labels")
        self.assertIsNotNone(t22_bb)
        self.assertEqual(sorted(t22_bb), ["Task 1.1", "Task 2.1"])


class TestPhaseSequenceMode(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scrum-v2-ps-"))
        self.plan = self.tmp / "plan.md"
        self.plan.write_text(PLAN_HAPPY)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_phase_sequence_ignores_override(self):
        proposer = _reload_proposer()
        proposal = proposer.build_proposal(
            self.plan, cli_project_override=None,
            cli_target_sprint="current", actor="test",
            dependency_mode="phase-sequence",
        )
        deps = proposal["computed_deps"]
        self.assertEqual(deps.get("Task 2.2", []), ["Task 1.2"])


class TestGateCheckFail(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scrum-v2-gate-"))
        self.plan = self.tmp / "plan.md"
        self.plan.write_text(PLAN_MISSING_AC)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_plan_missing_ac_raises_gate_check_failed(self):
        from lib import gate_check
        proposer = _reload_proposer()
        with self.assertRaises(gate_check.GateCheckFailedError) as ctx:
            proposer.build_proposal(
                self.plan, cli_project_override=None,
                cli_target_sprint="current", actor="test",
                dependency_mode="hybrid",
            )
        self.assertTrue(any("Task 1.1" in f for f in ctx.exception.failures))


if __name__ == "__main__":
    unittest.main()
